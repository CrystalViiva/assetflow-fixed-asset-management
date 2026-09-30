from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import transaction

from audit.models import AuditLog
from depreciation.constants import MONTHLY_DEPRECIATION_SCHEDULE_ID
from depreciation.models import (
    AccountingPeriod,
    DepreciationEntry,
    DepreciationRun,
    DepreciationRunStatus,
)
from depreciation.services import (
    create_accounting_period,
    execute_monthly_run,
    generate_depreciation_schedule,
    schedule_monthly_depreciation,
    schedule_organization_depreciation,
)


@pytest.mark.django_db(transaction=True)
def test_monthly_schedule_dispatches_once_after_commit(accountant, asset_factory):
    generate_depreciation_schedule(asset_id=asset_factory().pk, actor=accountant)
    create_accounting_period(actor=accountant, year=2025, month=2)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay") as enqueue:
        result = schedule_monthly_depreciation(window=date(2025, 2, 1))
    assert result["runs_created"] == 1
    assert enqueue.call_count == 1
    run = DepreciationRun.objects.get(organization=accountant.organization)
    assert run.status == DepreciationRunStatus.PENDING
    enqueue.assert_called_once_with(str(run.pk))


@pytest.mark.django_db(transaction=True)
def test_dispatch_waits_for_outer_commit_and_is_discarded_on_rollback(accountant, asset_factory):
    create_accounting_period(actor=accountant, year=2025, month=2)
    generate_depreciation_schedule(asset_id=asset_factory().pk, actor=accountant)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay") as enqueue:
        with transaction.atomic():
            run, created = schedule_organization_depreciation(
                accountant.organization, window=date(2025, 2, 1)
            )
            assert created
            enqueue.assert_not_called()
        enqueue.assert_called_once_with(str(run.pk))

        with pytest.raises(RuntimeError):
            with transaction.atomic():
                schedule_organization_depreciation(accountant.organization, window=date(2025, 3, 1))
                raise RuntimeError("force rollback")
        assert not DepreciationRun.objects.filter(scheduled_for=date(2025, 3, 1)).exists()
        assert enqueue.call_count == 1


@pytest.mark.django_db(transaction=True)
def test_repeated_scheduler_delivery_reuses_durable_monthly_run(accountant):
    create_accounting_period(actor=accountant, year=2025, month=2)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay") as enqueue:
        first = schedule_monthly_depreciation(window=date(2025, 2, 21))
        second = schedule_monthly_depreciation(window=date(2025, 2, 1))
    assert first["runs_created"] == 1
    assert second["runs_skipped_existing"] == 1
    assert first["run_ids"] == second["run_ids"]
    assert DepreciationRun.objects.filter(organization=accountant.organization).count() == 1
    assert enqueue.call_count == 2


@pytest.mark.django_db(transaction=True)
def test_monthly_task_creates_separate_runs_for_active_organizations(
    accountant, other_organization
):
    create_accounting_period(actor=accountant, year=2025, month=2)
    AccountingPeriod.objects.create(organization=other_organization, year=2025, month=2)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay") as enqueue:
        result = schedule_monthly_depreciation(window=date(2025, 2, 1))
    assert result["organizations_considered"] == 2
    assert result["runs_created"] == 2
    assert DepreciationRun.objects.filter(scheduled_for=date(2025, 2, 1)).count() == 2
    assert enqueue.call_count == 2


@pytest.mark.django_db(transaction=True)
def test_missing_and_closed_periods_are_recorded_without_dispatch(accountant):
    from organizations.models import Organization

    Organization.objects.exclude(pk=accountant.organization_id).update(is_active=False)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay") as enqueue:
        missing = schedule_monthly_depreciation(window=date(2025, 2, 1))
        assert missing["runs_not_dispatched"][0]["reason"] == "AccountingPeriodMissing"
        closed = create_accounting_period(actor=accountant, year=2025, month=3)
        from depreciation.services import close_accounting_period

        close_accounting_period(period_id=closed.pk, actor=accountant)
        closed_result = schedule_monthly_depreciation(window=date(2025, 3, 1))
    assert enqueue.call_count == 0
    assert DepreciationRun.objects.get(scheduled_for=date(2025, 2, 1)).failure_class == (
        "AccountingPeriodMissing"
    )
    assert DepreciationRun.objects.get(scheduled_for=date(2025, 3, 1)).failure_class == (
        "AccountingPeriodClosed"
    )
    assert closed_result["runs_not_dispatched"][0]["status"] == DepreciationRunStatus.FAILED


@pytest.mark.django_db(transaction=True)
def test_execution_uses_existing_posting_service_and_system_attribution(accountant, asset_factory):
    asset = asset_factory()
    generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    period = create_accounting_period(actor=accountant, year=2025, month=2)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay"):
        run, _ = schedule_organization_depreciation(
            accountant.organization, window=period.first_day
        )
    from depreciation.tasks import execute_monthly_depreciation_run

    result = execute_monthly_depreciation_run.run(str(run.pk))
    assert result["status"] == DepreciationRunStatus.COMPLETED
    entry = DepreciationEntry.objects.get(asset=asset, accounting_period=period)
    assert entry.created_by is None
    assert entry.depreciation_amount == Decimal("166666.67")
    event = AuditLog.objects.get(action="DEPRECIATION_POSTED", entity_id=str(entry.pk))
    assert event.user_id is None


@pytest.mark.django_db(transaction=True)
def test_completed_run_replay_is_idempotent(accountant, asset_factory):
    asset = asset_factory()
    generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    period = create_accounting_period(actor=accountant, year=2025, month=2)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay"):
        run, _ = schedule_organization_depreciation(
            accountant.organization, window=period.first_day
        )
    first = execute_monthly_run(run_id=run.pk)
    second = execute_monthly_run(run_id=run.pk)
    assert first == second
    assert DepreciationEntry.objects.filter(accounting_period=period).count() == 1


@pytest.mark.django_db(transaction=True)
def test_failed_run_is_terminal_and_scheduler_does_not_redispatch(accountant):
    schedule_monthly_depreciation(window=date(2025, 2, 1))
    run = DepreciationRun.objects.get(scheduled_for=date(2025, 2, 1))
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay") as enqueue:
        repeated = schedule_monthly_depreciation(window=date(2025, 2, 1))
        result = execute_monthly_run(run_id=run.pk)
    assert repeated["runs_skipped_existing"] == 1
    assert result["status"] == DepreciationRunStatus.FAILED
    enqueue.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_organization_isolation_and_future_schedule_is_not_a_failure(
    accountant, asset_factory, other_organization
):
    from accounts.models import User, UserRole
    from assets.models import Asset, AssetCategory, AssetStatus
    from organizations.models import Department

    current = asset_factory()
    generate_depreciation_schedule(asset_id=current.pk, actor=accountant)
    foreign_department = Department.objects.create(
        organization=other_organization, name="Other Finance", code="OTHERFIN"
    )
    foreign_category = AssetCategory.objects.create(
        organization=other_organization, name="Other", code="OTHER", default_useful_life_months=12
    )
    foreign_asset = Asset.objects.create(
        organization=other_organization,
        department=foreign_department,
        category=foreign_category,
        asset_tag="FOREIGN-DEPR",
        name="Foreign asset",
        status=AssetStatus.ACTIVE,
        acquisition_date="2025-01-01",
        capitalization_date="2025-01-01",
        available_for_use_date="2025-01-01",
        purchase_cost=Decimal("100.00"),
        residual_value=Decimal("0.00"),
        useful_life_months=1,
        current_book_value=Decimal("100.00"),
    )
    foreign_actor = User.objects.create_user(
        "other-accountant@example.com",
        "strong-password",
        organization=other_organization,
        department=foreign_department,
        role=UserRole.ACCOUNTANT,
    )
    generate_depreciation_schedule(asset_id=foreign_asset.pk, actor=foreign_actor)
    period = create_accounting_period(actor=accountant, year=2025, month=2)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay"):
        run, _ = schedule_organization_depreciation(
            accountant.organization, window=period.first_day
        )
    result = execute_monthly_run(run_id=run.pk)
    assert result["status"] == DepreciationRunStatus.COMPLETED
    assert DepreciationEntry.objects.filter(asset=current).count() == 1
    assert not DepreciationEntry.objects.filter(asset=foreign_asset).exists()


@pytest.mark.django_db(transaction=True)
def test_future_start_and_inactive_organization_are_skipped(
    accountant, asset_factory, other_organization
):
    other_organization.is_active = False
    other_organization.save(update_fields=("is_active",))
    future_asset = asset_factory(
        asset_tag="AST-FUTURE",
        acquisition_date="2024-12-15",
        available_for_use_date="2025-03-01",
        capitalization_date="2025-01-01",
    )
    generate_depreciation_schedule(asset_id=future_asset.pk, actor=accountant)
    period = create_accounting_period(actor=accountant, year=2025, month=2)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay"):
        scheduled = schedule_monthly_depreciation(window=period.first_day)
    run = DepreciationRun.objects.get(pk=scheduled["run_ids"][0])
    result = execute_monthly_run(run_id=run.pk)
    future_asset.refresh_from_db()
    assert result["status"] == DepreciationRunStatus.COMPLETED
    assert result["schedules_considered"] == 0
    assert future_asset.current_book_value == Decimal("12000000.00")
    assert DepreciationEntry.objects.count() == 0
    assert scheduled["organizations_considered"] == 1


@pytest.mark.django_db(transaction=True)
def test_behind_schedule_blocks_the_batch_without_catch_up(accountant, asset_factory):
    asset = asset_factory()
    generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    march = create_accounting_period(actor=accountant, year=2025, month=3)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay"):
        run, _ = schedule_organization_depreciation(accountant.organization, window=march.first_day)
    result = execute_monthly_run(run_id=run.pk)
    assert result["status"] == DepreciationRunStatus.FAILED
    assert result["failure_class"] == "ValueError"
    assert "next required period is 2025-02" in result["failure_message"]
    assert not DepreciationEntry.objects.filter(organization=accountant.organization).exists()


@pytest.mark.django_db(transaction=True)
def test_posting_failure_records_committed_partial_progress(accountant, asset_factory):
    first_asset = asset_factory(asset_tag="AST-BATCH-001")
    second_asset = asset_factory(asset_tag="AST-BATCH-002")
    generate_depreciation_schedule(asset_id=first_asset.pk, actor=accountant)
    generate_depreciation_schedule(asset_id=second_asset.pk, actor=accountant)
    period = create_accounting_period(actor=accountant, year=2025, month=2)
    with patch("depreciation.tasks.execute_monthly_depreciation_run.delay"):
        run, _ = schedule_organization_depreciation(
            accountant.organization, window=period.first_day
        )
    from depreciation.services import automation

    real_post = automation.post_depreciation

    def fail_second(*, asset_id, **kwargs):
        if asset_id == second_asset.pk:
            raise RuntimeError("posting failure")
        return real_post(asset_id=asset_id, **kwargs)

    with patch("depreciation.services.automation.post_depreciation", side_effect=fail_second):
        result = execute_monthly_run(run_id=run.pk)
    run.refresh_from_db()
    assert result["status"] == DepreciationRunStatus.FAILED
    assert run.entries_posted == 1
    assert run.total_depreciation_posted == Decimal("166666.67")
    assert DepreciationEntry.objects.filter(accounting_period=period).count() == 1


@pytest.mark.django_db(transaction=True)
def test_one_organization_failure_does_not_stop_other_organizations(accountant, other_organization):
    AccountingPeriod.objects.create(organization=accountant.organization, year=2025, month=2)
    AccountingPeriod.objects.create(organization=other_organization, year=2025, month=2)
    original = schedule_organization_depreciation

    def fail_first(organization, *, window):
        if organization.pk == accountant.organization_id:
            raise RuntimeError("isolated scheduling failure")
        return original(organization, window=window)

    with (
        patch(
            "depreciation.services.automation.schedule_organization_depreciation",
            side_effect=fail_first,
        ),
        patch("depreciation.tasks.execute_monthly_depreciation_run.delay"),
    ):
        result = schedule_monthly_depreciation(window=date(2025, 2, 1))
    assert result["organizations_failed"] == [
        {"organization_id": str(accountant.organization_id), "error_type": "RuntimeError"}
    ]
    assert DepreciationRun.objects.filter(organization=other_organization).exists()


def test_monthly_beat_schedule_is_registered_once_with_project_cadence():
    from django.conf import settings

    from config.celery import app

    matches = [
        value
        for key, value in app.conf.beat_schedule.items()
        if key == MONTHLY_DEPRECIATION_SCHEDULE_ID
    ]
    assert len(matches) == 1
    assert len(app.conf.beat_schedule) == 3
    assert app.conf.beat_schedule["recover-unfinished-assurance"] == {
        "task": "assurance.tasks.recover_assurance_runs",
        "schedule": 60.0,
    }
    assert matches[0]["task"] == "depreciation.tasks.schedule_monthly_depreciation_run"
    cadence = matches[0]["schedule"]
    assert cadence.day_of_month == {1}
    assert cadence.hour == {2}
    assert cadence.minute == {0}
    assert app.conf.timezone == settings.CELERY_TIMEZONE == settings.TIME_ZONE
