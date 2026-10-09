from datetime import date
from decimal import Decimal
from unittest.mock import call, patch

import pytest
from celery.schedules import crontab
from django.conf import settings
from django.db import IntegrityError, connection, transaction

from assets.models import Asset, AssetCategory, AssetCondition, AssetStatus
from assurance.constants import DAILY_FULL_SCHEDULE_ID
from assurance.models import AssuranceFinding, AssuranceRun, AssuranceRunStatus
from assurance.serializers import AssuranceRunSerializer
from assurance.services.runs import dispatch_run as dispatch_run_service
from assurance.tasks import schedule_daily_assurance
from assurance.tests.helpers import execute_to_completion
from audit.models import AuditLog
from config.celery import app
from depreciation.constants import MONTHLY_DEPRECIATION_SCHEDULE_ID
from organizations.models import Organization


@pytest.mark.django_db(transaction=True)
def test_one_active_organization_gets_a_durable_scheduled_run_and_existing_dispatch(
    manager,
):
    window = date(2026, 10, 1)

    def assert_dispatch_after_commit(*_args):
        assert not connection.in_atomic_block

    with (
        patch("assurance.services.scheduling.timezone.localdate", return_value=window),
        patch("assurance.services.scheduling.dispatch_run", wraps=dispatch_run_service) as dispatch,
        patch(
            "assurance.tasks.execute_assurance_run.delay",
            side_effect=assert_dispatch_after_commit,
        ) as enqueue,
    ):
        result = schedule_daily_assurance.run()

    run = AssuranceRun.objects.get(organization=manager.organization, scheduled_for=window)
    assert result["schedule_id"] == DAILY_FULL_SCHEDULE_ID
    assert result["window"] == window.isoformat()
    assert result["organizations_considered"] == 1
    assert result["runs_created"] == 1
    assert result["runs_skipped_existing"] == 0
    assert result["created_run_ids"] == [str(run.pk)]
    assert run.status == AssuranceRunStatus.RUNNING
    assert run.run_type == "FULL"
    assert run.started_by is None
    assert AssuranceRunSerializer(run).data["started_by_email"] is None
    assert AssuranceRunSerializer(run).data["scheduled_for"] == window.isoformat()
    dispatch.assert_called_once_with(run_id=run.pk, actor=None, organization=manager.organization)
    enqueue.assert_called_once_with(str(run.pk))

    task_result = execute_to_completion(str(run.pk))
    run.refresh_from_db()
    assert task_result["status"] == AssuranceRunStatus.COMPLETED
    assert run.completed_by is None
    start_event = AuditLog.objects.get(entity_id=str(run.pk), action="ASSURANCE_RUN_STARTED")
    assert start_event.user is None
    assert AuditLog.objects.filter(
        entity_id=str(run.pk), action="ASSURANCE_RUN_COMPLETED", user__isnull=True
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_repeated_scheduler_delivery_for_same_window_does_not_create_duplicate_runs(
    manager,
):
    window = date(2026, 10, 2)
    with (
        patch("assurance.services.scheduling.timezone.localdate", return_value=window),
        patch("assurance.tasks.execute_assurance_run.delay") as enqueue,
    ):
        first = schedule_daily_assurance.run()
        second = schedule_daily_assurance.run()

    assert first["runs_created"] == 1
    assert second["runs_created"] == 0
    assert second["runs_skipped_existing"] == 1
    assert len(second["existing_run_ids"]) == 1
    assert (
        AssuranceRun.objects.filter(organization=manager.organization, scheduled_for=window).count()
        == 1
    )
    enqueue.assert_has_calls([call(first["created_run_ids"][0]), call(first["created_run_ids"][0])])

    duplicate = AssuranceRun(
        organization=manager.organization,
        run_type="FULL",
        scheduled_for=window,
        started_by=None,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        duplicate.save()


@pytest.mark.django_db(transaction=True)
def test_each_active_organization_gets_an_isolated_scheduled_run(
    manager, other_organization, asset_factory
):
    asset_factory(current_book_value=Decimal("900.00"))
    other_category = AssetCategory.objects.create(
        organization=other_organization,
        code="OTHER-EQUIP",
        name="Other organization equipment",
        default_useful_life_months=60,
    )
    Asset.objects.create(
        organization=other_organization,
        category=other_category,
        asset_tag="OTHER-ASSET-001",
        name="Other organization asset",
        status=AssetStatus.ACTIVE,
        condition=AssetCondition.GOOD,
        acquisition_date=date(2022, 1, 1),
        capitalization_date=date(2022, 1, 1),
        available_for_use_date=date(2022, 1, 1),
        purchase_cost=Decimal("1000.00"),
        residual_value=Decimal("100.00"),
        current_book_value=Decimal("900.00"),
        accumulated_depreciation=Decimal("0.00"),
        useful_life_months=60,
    )
    window = date(2026, 10, 3)

    with (
        patch("assurance.services.scheduling.timezone.localdate", return_value=window),
        patch("assurance.tasks.execute_assurance_run.delay"),
    ):
        result = schedule_daily_assurance.run()

    runs = list(AssuranceRun.objects.filter(scheduled_for=window).order_by("organization_id"))
    assert result["organizations_considered"] == 2
    assert result["runs_created"] == 2
    assert {run.organization_id for run in runs} == {
        manager.organization_id,
        other_organization.pk,
    }

    results_by_org = {str(run.organization_id): execute_to_completion(str(run.pk)) for run in runs}
    assert results_by_org[str(manager.organization_id)]["assets_evaluated"] == 1
    assert results_by_org[str(other_organization.pk)]["assets_evaluated"] == 1
    for run in runs:
        assert (
            not AssuranceFinding.objects.filter(last_detected_run=run)
            .exclude(organization_id=run.organization_id)
            .exists()
        )


@pytest.mark.django_db(transaction=True)
def test_inactive_organizations_are_not_scheduled(manager, other_organization):
    other_organization.is_active = False
    other_organization.save(update_fields=("is_active", "updated_at"))
    window = date(2026, 10, 4)

    with (
        patch("assurance.services.scheduling.timezone.localdate", return_value=window),
        patch("assurance.tasks.execute_assurance_run.delay"),
    ):
        result = schedule_daily_assurance.run()

    assert result["organizations_considered"] == 1
    assert (
        AssuranceRun.objects.filter(organization=manager.organization, scheduled_for=window).count()
        == 1
    )
    assert not AssuranceRun.objects.filter(
        organization=other_organization, scheduled_for=window
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_one_organization_failure_is_reported_and_does_not_stop_others(
    manager, other_organization, caplog
):
    window = date(2026, 10, 5)
    organization_ids = list(
        Organization.objects.filter(is_active=True).order_by("pk").values_list("pk", flat=True)
    )
    failed_organization_id = organization_ids[0]
    actual_dispatch = dispatch_run_service

    def fail_one_organization(*, run_id, actor, organization):
        if organization.pk == failed_organization_id:
            raise RuntimeError("controlled dispatch failure")
        return actual_dispatch(run_id=run_id, actor=actor, organization=organization)

    with (
        patch("assurance.services.scheduling.timezone.localdate", return_value=window),
        patch("assurance.services.scheduling.dispatch_run", side_effect=fail_one_organization),
        patch("assurance.tasks.execute_assurance_run.delay"),
    ):
        result = schedule_daily_assurance.run()

    assert result["organizations_considered"] == 2
    assert result["runs_created"] == 2
    assert result["organizations_failed"] == [
        {"organization_id": str(failed_organization_id), "error_type": "RuntimeError"}
    ]
    assert "Scheduled assurance failed for organization" in caplog.text
    assert (
        AssuranceRun.objects.filter(organization_id=organization_ids[1], scheduled_for=window)
        .get()
        .status
        == AssuranceRunStatus.RUNNING
    )


def test_celery_beat_retains_daily_full_assurance_schedule():
    schedule = app.conf.beat_schedule

    assert DAILY_FULL_SCHEDULE_ID in schedule
    assert MONTHLY_DEPRECIATION_SCHEDULE_ID in schedule
    assert len(schedule) == 9
    assert schedule["identity-mail"]["task"] == "accounts.tasks.deliver_identity_mail"
    assert schedule["billing-reconciliation"]["task"] == "commercial.tasks.reconcile_billing"
    assert schedule["operational-heartbeat"]["task"] == "operations.tasks.heartbeat"
    assert schedule["recover-report-exports"]["task"] == "reporting.tasks.recover_report_exports"
    assert schedule["expire-report-exports"]["task"] == "reporting.tasks.expire_report_exports"
    assert schedule["clean-stale-evidence-uploads"]["task"] == (
        "verification.tasks.clean_stale_evidence_uploads"
    )
    entry = schedule[DAILY_FULL_SCHEDULE_ID]
    assert entry["task"] == "assurance.tasks.schedule_daily_assurance"
    assert isinstance(entry["schedule"], crontab)
    assert entry["schedule"].hour == {1}
    assert entry["schedule"].minute == {0}
    assert settings.CELERY_TIMEZONE == settings.TIME_ZONE
    assert app.conf.timezone == settings.TIME_ZONE
