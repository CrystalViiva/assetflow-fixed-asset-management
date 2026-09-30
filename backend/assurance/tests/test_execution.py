"""PostgreSQL execution contracts, including transaction and process boundaries."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import OperationalError, close_old_connections, connection, connections, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from assets.models import Asset
from assurance.models import (
    AssuranceFinding,
    AssuranceFindingOccurrence,
)
from assurance.services import create_run, execute_run
from assurance.services.execution import advance_run, recover_unfinished_runs
from assurance.services.inputs import candidate_from_payload
from assurance.services.runs import _asset_population, _collect_candidates
from verification.services import complete_campaign

pytestmark = pytest.mark.django_db(transaction=True)


def step(run, actor):
    return advance_run(run_id=run.pk, actor=actor)


def normalize(candidates):
    return sorted(
        (asdict(c) for c in candidates), key=lambda c: (c["identity_key"], c["finding_type"])
    )


@pytest.mark.parametrize("run_type", ("FULL", "PHYSICAL", "FINANCIAL", "OPERATIONAL"))
def test_equivalence_and_global_unicode_duplicates(
    manager,
    asset_factory,
    campaign_factory,
    observation_factory,
    settings,
    run_type,
):
    settings.ASSURANCE_WORK_UNIT_SIZE = 1
    one = asset_factory(current_book_value=Decimal("900"))
    two = asset_factory()
    asset_factory()  # Missing physical verification.
    campaign = campaign_factory()
    observation_factory(campaign, one, observed_asset_tag=" Straße ")
    observation_factory(campaign, two, observed_asset_tag="STRASSE")
    observation_factory(campaign, None, observed_asset_tag="strasse")
    complete_campaign(campaign_id=campaign.pk, actor=manager)
    run = create_run(actor=manager, run_type=run_type, verification_campaign=campaign)
    run = step(run, manager)
    expected = normalize(_collect_candidates(run, list(_asset_population(run))))
    while run.execution_phase == "EVALUATE":
        run = step(run, manager)
    actual = normalize(candidate_from_payload(c.payload) for c in run.candidates.all())
    assert actual == expected
    assert not AssuranceFinding.objects.exists()
    run = step(run, manager)
    assert run.status == "COMPLETED"
    if run_type != "FINANCIAL":
        assert run.candidates.filter(finding_type="DUPLICATE_TAG").count() == 3


def test_latest_tie_breaker_and_campaign_grouping(
    manager,
    asset_factory,
    campaign_factory,
    observation_factory,
    settings,
):
    settings.ASSURANCE_WORK_UNIT_SIZE = 1
    one, two = asset_factory(), asset_factory()
    a, b = campaign_factory(), campaign_factory()
    first = observation_factory(a, one, observed_asset_tag="SAME")
    second = observation_factory(b, one, observed_asset_tag="different")
    observation_factory(b, two, observed_asset_tag="SAME")
    # Deliberately equal timestamps; observation facts remain immutable via normal APIs.
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE verification_physicalverification SET verified_at=%s, created_at=%s "
            "WHERE id IN (%s,%s)",
            [first.verified_at, first.created_at, first.pk, second.pk],
        )
    run = create_run(actor=manager, run_type="OPERATIONAL")
    run = step(run, manager)
    selected = run.inputs.get(kind="OBSERVATION", asset_id=one.pk)
    assert selected.source_id == max(first.pk, second.pk)
    expected = normalize(_collect_candidates(run, list(_asset_population(run))))
    run = execute_run(run_id=run.pk, actor=manager)
    assert normalize(candidate_from_payload(c.payload) for c in run.candidates.all()) == expected
    assert run.candidates.filter(finding_type="DUPLICATE_TAG").count() == 0


def test_sealed_values_ignore_live_changes(manager, asset_factory, settings):
    settings.ASSURANCE_WORK_UNIT_SIZE = 1
    asset = asset_factory(current_book_value=Decimal("900"))
    run = step(create_run(actor=manager, run_type="FULL"), manager)
    payload = run.inputs.get(kind="ASSET").payload
    Asset.objects.filter(pk=asset.pk).update(current_book_value=Decimal("1000"))
    asset_factory()
    asset.department.name = "Renamed after capture"
    asset.department.save()
    run = execute_run(run_id=run.pk, actor=manager)
    assert run.assets_evaluated == 1
    assert run.inputs.get(kind="ASSET").payload == payload
    assert run.candidates.filter(finding_type="BOOK_VALUE_EXCEPTION").exists()


def test_capture_repeatable_read_and_no_asset_update_lock(manager, asset_factory, monkeypatch):
    from assurance.services import inputs

    asset = asset_factory(current_book_value=Decimal("900"))
    original = inputs.capture_observations
    observed = []

    def capture_then_change(run, size):
        with connection.cursor() as cursor:
            cursor.execute("SHOW transaction_isolation")
            observed.append(cursor.fetchone()[0])
        result = original(run, size)

        def edit():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '2s'")
                    Asset.objects.filter(pk=asset.pk).update(current_book_value=Decimal("1000"))
            finally:
                connections.close_all()

        with ThreadPoolExecutor(1) as pool:
            pool.submit(edit).result(timeout=10)
        return result

    monkeypatch.setattr(inputs, "capture_observations", capture_then_change)
    with CaptureQueriesContext(connection) as queries:
        run = step(create_run(actor=manager, run_type="FULL"), manager)
    assert run.status == "RUNNING"
    assert observed == ["repeatable read"]
    assert run.inputs.get(kind="ASSET").payload["asset"]["current_book_value"] == "900.00"
    assert not any('FOR UPDATE OF "assets_asset"' in q["sql"] for q in queries)


def test_interrupted_unit_retains_previous_progress(manager, asset_factory, settings, monkeypatch):
    from assurance.services import execution

    settings.ASSURANCE_WORK_UNIT_SIZE = 1
    for _ in range(3):
        asset_factory(current_book_value=Decimal("900"))
    run = step(create_run(actor=manager, run_type="FULL"), manager)
    run = step(run, manager)
    committed = list(run.candidates.values_list("pk", flat=True))
    original = execution._evaluate_unit

    def interrupt(run):
        original(run)
        raise SystemExit("simulated process interruption")

    with monkeypatch.context() as scoped:
        scoped.setattr(execution, "_evaluate_unit", interrupt)
        with pytest.raises(SystemExit):
            step(run, manager)
    run.refresh_from_db()
    assert run.units_completed == 1
    assert list(run.candidates.values_list("pk", flat=True)) == committed
    assert not AssuranceFinding.objects.exists()
    run = execute_run(run_id=run.pk, actor=manager)
    assert run.status == "COMPLETED"
    assert run.finding_occurrences.count() == 6


def test_failure_after_completed_units_and_publication_rollback(
    manager,
    asset_factory,
    settings,
    monkeypatch,
):
    import assurance.services.runs as services

    settings.ASSURANCE_WORK_UNIT_SIZE = 1
    for _ in range(2):
        asset_factory(current_book_value=Decimal("900"))
    run = step(create_run(actor=manager, run_type="FULL"), manager)
    while run.execution_phase == "EVALUATE":
        run = step(run, manager)
    original = services._record_candidate
    count = 0

    def fail(*args, **kwargs):
        nonlocal count
        result = original(*args, **kwargs)
        count += 1
        if count == 2:
            raise RuntimeError("publication failure")
        return result

    monkeypatch.setattr(services, "_record_candidate", fail)
    run = step(run, manager)
    assert run.status == "FAILED"
    assert run.units_completed == 2
    assert run.candidates.count() == 4
    assert not AssuranceFinding.objects.exists()
    assert not AssuranceFindingOccurrence.objects.exists()


def test_transient_retry_and_exhaustion(manager, asset_factory, settings, monkeypatch):
    from assurance.services import execution

    settings.ASSURANCE_RETRY_SECONDS = 0
    settings.ASSURANCE_MAX_TRANSIENT_RETRIES = 1
    asset_factory()
    run = step(create_run(actor=manager, run_type="FULL"), manager)
    with monkeypatch.context() as scoped:
        scoped.setattr(
            execution, "_evaluate_unit", lambda run: (_ for _ in ()).throw(OperationalError())
        )
        run = step(run, manager)
        assert run.status == "RUNNING" and run.retry_count == 1
    run = execute_run(run_id=run.pk, actor=manager)
    assert run.status == "COMPLETED" and run.retry_count == 0
    run = step(create_run(actor=manager, run_type="FULL"), manager)
    monkeypatch.setattr(
        execution, "_evaluate_unit", lambda run: (_ for _ in ()).throw(OperationalError())
    )
    run = step(run, manager)
    run = step(run, manager)
    assert run.status == "FAILED"
    assert not run.finding_occurrences.exists()


def test_missing_unit_blocks_completion(manager, asset_factory):
    asset_factory()
    run = step(create_run(actor=manager, run_type="FULL"), manager)
    run = step(run, manager)
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM assurance_assuranceworkunit WHERE run_id=%s", [run.pk])
    run = step(run, manager)
    assert run.status == "FAILED"
    assert not run.finding_occurrences.exists()


def test_recovery_and_legacy_running_are_separate(manager, asset_factory):
    asset_factory()
    run = step(create_run(actor=manager, run_type="FULL"), manager)
    legacy = create_run(actor=manager, run_type="FULL")
    legacy.executor_version = 0
    legacy.status = "RUNNING"
    legacy.started_at = timezone.now()
    legacy.save()
    with patch("assurance.tasks.execute_assurance_run.delay") as enqueue:
        assert recover_unfinished_runs() == 1
        enqueue.assert_called_once_with(str(run.pk))
    with pytest.raises(ValidationError, match="operator review"):
        step(legacy, manager)
    assert not legacy.inputs.exists()


def test_pending_legacy_upgrade_and_incompatible_seal(manager, asset_factory):
    asset_factory()
    run = create_run(actor=manager, run_type="FULL")
    run.executor_version = 0
    run.save()
    run = step(run, manager)
    assert run.executor_version == 1 and run.input_schema_version == 1
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE assurance_assurancerun SET input_schema_version=99 WHERE id=%s", [run.pk]
        )
    run = step(run, manager)
    assert run.status == "FAILED"
    assert not run.finding_occurrences.exists()


def test_concurrent_different_run_insertions(manager, asset_factory, monkeypatch):
    asset_factory(current_book_value=Decimal("900"))
    runs = [create_run(actor=manager, run_type="FINANCIAL") for _ in range(2)]
    for i, run in enumerate(runs):
        run = step(run, manager)
        runs[i] = step(run, manager)
    barrier = Barrier(2)
    original = AssuranceFinding.full_clean

    def wait_before_insert(self, *args, **kwargs):
        original(self, *args, **kwargs)
        if self.finding_type == "BOOK_VALUE_EXCEPTION":
            barrier.wait(timeout=20)

    monkeypatch.setattr(AssuranceFinding, "full_clean", wait_before_insert)

    def publish(run):
        close_old_connections()
        try:
            return step(run, manager).status
        finally:
            connections.close_all()

    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(publish, runs)) == ["COMPLETED", "COMPLETED"]
    assert AssuranceFinding.objects.count() == 2
    assert set(AssuranceFinding.objects.values_list("occurrence_count", flat=True)) == {2}
    assert AssuranceFindingOccurrence.objects.count() == 4


def test_tenant_and_snapshot_immutability(manager, foreign_manager, asset_factory):
    asset_factory()
    run = step(create_run(actor=manager, run_type="FULL"), manager)
    with pytest.raises(ValidationError):
        step(run, foreign_manager)
    row = run.inputs.first()
    with pytest.raises(ValidationError):
        row.save()
    with pytest.raises(ValidationError):
        run.inputs.update(payload={})
    run.scope = {"scope_type": "ORGANIZATION"}
    with pytest.raises(ValidationError):
        run.save()


def test_department_population_cannot_broaden(
    manager,
    asset_factory,
    campaign_factory,
    other_department,
    settings,
):
    settings.ASSURANCE_WORK_UNIT_SIZE = 1
    inside = asset_factory()
    outside = asset_factory(department=other_department)
    campaign = campaign_factory(scope_type="DEPARTMENT")
    complete_campaign(campaign_id=campaign.pk, actor=manager)
    run = step(
        create_run(actor=manager, run_type="PHYSICAL", verification_campaign=campaign), manager
    )
    Asset.objects.filter(pk=inside.pk).update(department=other_department)
    Asset.objects.filter(pk=outside.pk).update(department=campaign.department)
    run = execute_run(run_id=run.pk, actor=manager)
    assert run.status == "COMPLETED" and run.assets_evaluated == 1
    assert set(run.inputs.filter(kind="ASSET").values_list("source_id", flat=True)) == {inside.pk}


def test_publication_rollback_preserves_existing_findings(manager, asset_factory, monkeypatch):
    import assurance.services.runs as services

    asset_factory(current_book_value="900.00")
    first = execute_run(run_id=create_run(actor=manager, run_type="FULL").pk, actor=manager)
    before = list(
        AssuranceFinding.objects.order_by("pk").values(
            "pk", "occurrence_count", "last_detected_run_id", "observed_value"
        )
    )
    run = step(create_run(actor=manager, run_type="FULL"), manager)
    run = step(run, manager)
    original = services._record_candidate

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("rollback update")

    monkeypatch.setattr(services, "_record_candidate", fail)
    run = step(run, manager)
    assert run.status == "FAILED"
    assert (
        list(
            AssuranceFinding.objects.order_by("pk").values(
                "pk", "occurrence_count", "last_detected_run_id", "observed_value"
            )
        )
        == before
    )
    assert not run.finding_occurrences.exists()
    assert first.finding_occurrences.count() == 2


def test_late_completion_does_not_regress_latest_detection(manager, asset_factory):
    asset = asset_factory(current_book_value="900.00")
    old = step(create_run(actor=manager, run_type="FINANCIAL"), manager)
    Asset.objects.filter(pk=asset.pk).update(current_book_value="800.00")
    new = execute_run(run_id=create_run(actor=manager, run_type="FINANCIAL").pk, actor=manager)
    old = execute_run(run_id=old.pk, actor=manager)
    finding = AssuranceFinding.objects.get(asset=asset, finding_type="BOOK_VALUE_EXCEPTION")
    assert finding.last_detected_run_id == new.pk and finding.occurrence_count == 2
    assert finding.observed_value == "800.00"
    assert old.finding_occurrences.get(finding=finding).observed_value == "900.00"


def test_each_task_phase_and_duplicate_delivery(manager, asset_factory):
    from assurance.tasks import execute_assurance_run

    asset_factory()
    run = create_run(actor=manager, run_type="FULL")
    assert execute_assurance_run.run(str(run.pk))["status"] == "RUNNING"
    run.refresh_from_db()
    assert run.execution_phase == "EVALUATE" and run.sealed_at
    assert execute_assurance_run.run(str(run.pk))["status"] == "RUNNING"
    run.refresh_from_db()
    assert run.units_completed == 1 and run.execution_phase == "PUBLISH"
    result = execute_assurance_run.run(str(run.pk))
    assert result["status"] == "COMPLETED"
    assert execute_assurance_run.run(str(run.pk)) == result
    assert run.candidates.count() == run.finding_occurrences.count() == 1


def test_same_run_unit_claim_is_serialized(manager, asset_factory, settings):
    settings.ASSURANCE_WORK_UNIT_SIZE = 1
    for _ in range(2):
        asset_factory()
    run = step(create_run(actor=manager, run_type="FULL"), manager)
    barrier = Barrier(2)

    def evaluate():
        close_old_connections()
        try:
            barrier.wait(timeout=15)
            return step(run, manager).status
        finally:
            connections.close_all()

    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(lambda _: evaluate(), range(2))) == ["RUNNING", "RUNNING"]
    run.refresh_from_db()
    assert run.units_completed == 2
    assert run.candidates.count() == 2
    assert not run.finding_occurrences.exists()


def test_financial_equivalence_with_schedule_and_ledger(manager, asset_factory):
    from datetime import date

    from depreciation.models import DepreciationSchedule

    asset = asset_factory(current_book_value="700.00", accumulated_depreciation="50.00")
    DepreciationSchedule.objects.create(
        organization=manager.organization,
        asset=asset,
        method="SLM",
        capitalized_cost="1100.00",
        depreciable_base="1000.00",
        residual_value="100.00",
        useful_life_months=60,
        start_date=date(2022, 1, 1),
        end_date=date(2026, 12, 31),
        periodic_depreciation="16.67",
        status="COMPLETE",
    )
    run = step(create_run(actor=manager, run_type="FINANCIAL"), manager)
    expected = normalize(_collect_candidates(run, list(_asset_population(run))))
    run = execute_run(run_id=run.pk, actor=manager)
    assert run.status == "COMPLETED"
    assert normalize(candidate_from_payload(c.payload) for c in run.candidates.all()) == expected
