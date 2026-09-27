from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.utils import timezone

from assets.models import AssetStatus
from assurance.models import (
    AssuranceFinding,
    AssuranceRun,
    AssuranceRunStatus,
    AssuranceRunType,
    FindingStatus,
    FindingType,
)
from assurance.services import (
    create_run,
    execute_run,
    reject_finding,
    resolve_finding,
    review_finding,
)
from verification.models import (
    EvidenceType,
    ExceptionSeverity,
    PhysicalCondition,
    VerificationEvidence,
)
from verification.services import complete_campaign, create_manual_exception


@pytest.mark.django_db
def test_physical_run_reconciles_observation_without_changing_asset(
    manager,
    asset_factory,
    campaign_factory,
    observation_factory,
    other_department,
    other_location,
):
    asset = asset_factory()
    campaign = campaign_factory()
    observation = observation_factory(
        campaign,
        asset,
        observed_department=other_department,
        observed_location=other_location,
        observed_condition=PhysicalCondition.DAMAGED,
        observed_asset_tag="WRONG-TAG",
    )
    complete_campaign(campaign_id=campaign.pk, actor=manager)
    before = (asset.department_id, asset.location_id, asset.condition, asset.asset_tag)

    run = create_run(
        actor=manager,
        run_type=AssuranceRunType.PHYSICAL,
        verification_campaign=campaign,
    )
    run = execute_run(run_id=run.pk, actor=manager)

    assert run.status == AssuranceRunStatus.COMPLETED
    assert run.assets_evaluated == 1
    assert set(
        AssuranceFinding.objects.filter(last_detected_run=run).values_list(
            "finding_type", flat=True
        )
    ) >= {
        FindingType.DEPARTMENT_MISMATCH,
        FindingType.LOCATION_MISMATCH,
        FindingType.CONDITION_EXCEPTION,
        FindingType.TAG_MISMATCH,
    }
    asset.refresh_from_db()
    assert (asset.department_id, asset.location_id, asset.condition, asset.asset_tag) == before
    assert observation.asset_id == asset.pk
    assert (
        AssuranceFinding.objects.get(
            last_detected_run=run, finding_type=FindingType.LOCATION_MISMATCH
        ).physical_verification_id
        == observation.pk
    )


@pytest.mark.django_db
def test_physical_run_finds_missing_registered_and_unregistered_items(
    manager, asset_factory, campaign_factory, observation_factory
):
    missing = asset_factory()
    campaign = campaign_factory()
    unregistered_observation = observation_factory(
        campaign, None, observed_asset_tag="FOUND-UNREGISTERED"
    )
    create_manual_exception(
        actor=manager,
        verification_id=unregistered_observation.pk,
        severity=ExceptionSeverity.HIGH,
        description="Unregistered item requires follow-up evidence",
    )
    complete_campaign(campaign_id=campaign.pk, actor=manager)
    run = create_run(
        actor=manager,
        run_type=AssuranceRunType.PHYSICAL,
        verification_campaign=campaign,
    )

    run = execute_run(run_id=run.pk, actor=manager)

    types = set(
        AssuranceFinding.objects.filter(last_detected_run=run).values_list(
            "finding_type", flat=True
        )
    )
    assert FindingType.MISSING_PHYSICAL_VERIFICATION in types
    assert FindingType.UNREGISTERED_ASSET in types
    unregistered_finding = AssuranceFinding.objects.get(
        last_detected_run=run, finding_type=FindingType.UNREGISTERED_ASSET
    )
    assert unregistered_finding.asset_id is None
    assert unregistered_finding.physical_verification_id == unregistered_observation.pk
    assert AssuranceFinding.objects.filter(
        last_detected_run=run,
        finding_type=FindingType.MISSING_EVIDENCE,
        physical_verification_id=unregistered_observation.pk,
    ).exists()
    assert missing.pk in set(
        AssuranceFinding.objects.filter(last_detected_run=run).values_list("asset_id", flat=True)
    )


@pytest.mark.django_db
def test_physical_run_detects_duplicate_tag_and_missing_evidence(
    manager, asset_factory, campaign_factory, observation_factory
):
    first, second = asset_factory(), asset_factory()
    campaign = campaign_factory()
    one = observation_factory(campaign, first, observed_asset_tag="DUPLICATE")
    observation_factory(campaign, second, observed_asset_tag="DUPLICATE")
    create_manual_exception(
        actor=manager,
        verification_id=one.pk,
        severity=ExceptionSeverity.HIGH,
        description="Observed significant damage",
    )
    VerificationEvidence.objects.create(
        organization=manager.organization,
        verification=one,
        evidence_type=EvidenceType.NOTE,
        captured_by=manager,
        description="Reviewer note retained as evidence metadata",
    )
    complete_campaign(campaign_id=campaign.pk, actor=manager)
    run = create_run(
        actor=manager,
        run_type=AssuranceRunType.PHYSICAL,
        verification_campaign=campaign,
    )
    run = execute_run(run_id=run.pk, actor=manager)

    findings = AssuranceFinding.objects.filter(last_detected_run=run)
    assert findings.filter(finding_type=FindingType.DUPLICATE_TAG).count() == 2
    assert findings.filter(finding_type=FindingType.MISSING_EVIDENCE).count() == 1


@pytest.mark.django_db
def test_full_run_deduplicates_occurrences_and_reopens_resolved_history(manager, asset_factory):
    asset = asset_factory(current_book_value=Decimal("900.00"))

    def run_full():
        run = create_run(actor=manager, run_type=AssuranceRunType.FULL)
        return execute_run(run_id=run.pk, actor=manager)

    first_run = run_full()
    finding = AssuranceFinding.objects.get(
        asset=asset, finding_type=FindingType.BOOK_VALUE_EXCEPTION
    )
    assert finding.occurrence_count == 1
    second_run = run_full()
    finding.refresh_from_db()
    assert finding.occurrence_count == 2
    assert finding.occurrences.count() == 2
    assert finding.last_detected_run_id == second_run.pk
    assert first_run.findings_generated == 2

    review_finding(finding_id=finding.pk, actor=manager)
    resolve_finding(finding_id=finding.pk, actor=manager, resolution_notes="Reviewed ledger basis")
    asset.current_book_value = Decimal("1000.00")
    asset.save(update_fields=("current_book_value", "updated_at"))
    run_full()
    asset.current_book_value = Decimal("900.00")
    asset.save(update_fields=("current_book_value", "updated_at"))
    reappeared_run = run_full()

    reopened = AssuranceFinding.objects.get(
        asset=asset,
        finding_type=FindingType.BOOK_VALUE_EXCEPTION,
        last_detected_run=reappeared_run,
    )
    assert reopened.pk != finding.pk
    assert reopened.status == FindingStatus.OPEN
    assert reopened.occurrence_count == 1
    finding.refresh_from_db()
    assert finding.status == FindingStatus.RESOLVED
    assert first_run.assets_evaluated == 1


@pytest.mark.django_db
def test_failed_execution_rolls_back_findings_but_keeps_failed_run(
    monkeypatch, manager, asset_factory
):
    asset_factory(current_book_value=Decimal("900.00"))
    run = create_run(actor=manager, run_type=AssuranceRunType.FULL)
    import assurance.services.runs as run_services

    record_candidate = run_services._record_candidate
    inserted = 0

    def fail_after_candidate(*args, **kwargs):
        nonlocal inserted
        inserted += 1
        if inserted == 2:
            raise RuntimeError("controlled test failure")
        return record_candidate(*args, **kwargs)

    monkeypatch.setattr("assurance.services.runs._record_candidate", fail_after_candidate)
    result = execute_run(run_id=run.pk, actor=manager)

    assert result.status == AssuranceRunStatus.FAILED
    assert result.failure_message == "Evaluation failed (RuntimeError)."
    assert inserted == 2
    assert not AssuranceFinding.objects.filter(organization=manager.organization).exists()


@pytest.mark.django_db
def test_completed_run_reexecution_returns_same_run_without_new_occurrences(manager, asset_factory):
    asset_factory(current_book_value=Decimal("900.00"))
    run = execute_run(
        run_id=create_run(actor=manager, run_type=AssuranceRunType.FULL).pk,
        actor=manager,
    )
    before = list(
        run.findings.order_by("pk").values_list("pk", "occurrence_count", "last_detected_run_id")
    )

    repeated = execute_run(run_id=run.pk, actor=manager)

    after = list(
        run.findings.order_by("pk").values_list("pk", "occurrence_count", "last_detected_run_id")
    )
    assert repeated.pk == run.pk
    assert repeated.status == AssuranceRunStatus.COMPLETED
    assert after == before


@pytest.mark.django_db
def test_running_run_can_be_reentered_after_worker_transaction_rollback(manager, asset_factory):
    asset_factory(current_book_value=Decimal("900.00"))
    run = create_run(actor=manager, run_type=AssuranceRunType.FULL)
    run.status = AssuranceRunStatus.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=("status", "started_at", "updated_at"))

    completed = execute_run(run_id=run.pk, actor=manager)

    assert completed.status == AssuranceRunStatus.COMPLETED
    assert completed.findings.count() == 2
    assert completed.findings.first().occurrences.count() == 1


@pytest.mark.django_db
def test_failed_run_is_terminal_and_retry_requires_a_new_run(monkeypatch, manager, asset_factory):
    asset_factory(current_book_value=Decimal("900.00"))
    run = create_run(actor=manager, run_type=AssuranceRunType.FULL)

    def fail_candidates(*args, **kwargs):
        raise RuntimeError("controlled failure")

    monkeypatch.setattr("assurance.services.runs._collect_candidates", fail_candidates)
    failed = execute_run(run_id=run.pk, actor=manager)

    with pytest.raises(ValidationError, match="terminal"):
        execute_run(run_id=run.pk, actor=manager)

    assert failed.status == AssuranceRunStatus.FAILED
    assert not AssuranceFinding.objects.filter(assurance_run=run).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_execution_attempts_create_one_occurrence(manager, asset_factory):
    asset = asset_factory(current_book_value=Decimal("900.00"))
    run = create_run(actor=manager, run_type=AssuranceRunType.FULL)
    barrier = Barrier(2)

    def execute_concurrently():
        close_old_connections()
        try:
            from accounts.models import User

            actor = User.objects.get(pk=manager.pk)
            barrier.wait(timeout=10)
            return execute_run(run_id=run.pk, actor=actor).status
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: execute_concurrently(), range(2)))

    assert results == [AssuranceRunStatus.COMPLETED, AssuranceRunStatus.COMPLETED]
    finding = AssuranceFinding.objects.get(
        asset=asset, finding_type=FindingType.BOOK_VALUE_EXCEPTION
    )
    assert finding.occurrence_count == 1
    assert finding.occurrences.count() == 1


@pytest.mark.django_db
def test_org_isolation_and_campaign_organization_validation(
    manager, foreign_manager, asset_factory, other_organization
):
    run = create_run(actor=manager, run_type=AssuranceRunType.FULL)
    with pytest.raises(ValidationError):
        execute_run(run_id=run.pk, actor=foreign_manager)
    assert not AssuranceRun.objects.filter(organization=other_organization).exists()


@pytest.mark.django_db
def test_financial_controls_flag_missing_schedule_and_book_value(manager, asset_factory):
    asset = asset_factory(current_book_value=Decimal("900.00"))
    run = create_run(actor=manager, run_type=AssuranceRunType.FINANCIAL)

    run = execute_run(run_id=run.pk, actor=manager)

    found = set(
        AssuranceFinding.objects.filter(last_detected_run=run).values_list(
            "finding_type", flat=True
        )
    )
    assert FindingType.DEPRECIATION_EXCEPTION in found
    assert FindingType.BOOK_VALUE_EXCEPTION in found
    assert asset.current_book_value == Decimal("900.00")


@pytest.mark.django_db
def test_finding_review_resolution_acceptance_and_rejection_are_terminal(manager, asset_factory):
    asset_factory(current_book_value=Decimal("900.00"))
    run = execute_run(
        run_id=create_run(actor=manager, run_type=AssuranceRunType.FULL).pk,
        actor=manager,
    )
    finding = AssuranceFinding.objects.get(
        last_detected_run=run, finding_type=FindingType.BOOK_VALUE_EXCEPTION
    )
    review_finding(finding_id=finding.pk, actor=manager)
    resolved = resolve_finding(
        finding_id=finding.pk, actor=manager, resolution_notes="Corrected outside this system"
    )
    assert resolved.status == FindingStatus.RESOLVED
    with pytest.raises(ValidationError):
        reject_finding(finding_id=finding.pk, actor=manager, resolution_notes="No")


@pytest.mark.django_db
def test_stale_record_threshold_is_explicit_run_parameter(manager, asset_factory):
    asset = asset_factory()
    type(asset).objects.filter(pk=asset.pk).update(updated_at=timezone.now() - timedelta(days=40))
    run = create_run(actor=manager, run_type=AssuranceRunType.OPERATIONAL, stale_after_days=30)
    run = execute_run(run_id=run.pk, actor=manager)
    assert AssuranceFinding.objects.filter(
        last_detected_run=run, finding_type=FindingType.STALE_RECORD
    ).exists()


@pytest.mark.django_db
def test_custody_rule_compares_active_assignment_with_observed_custodian(
    manager, employee, asset_factory, campaign_factory, observation_factory
):
    from transfers.models import AssetAssignment

    asset = asset_factory()
    campaign = campaign_factory()
    observation_factory(campaign, asset, observed_custodian=employee)
    AssetAssignment.objects.create(
        organization=manager.organization,
        asset=asset,
        assigned_to=manager,
        department=asset.department,
        location=asset.location,
        created_by=manager,
    )
    complete_campaign(campaign_id=campaign.pk, actor=manager)
    run = create_run(
        actor=manager,
        run_type=AssuranceRunType.PHYSICAL,
        verification_campaign=campaign,
    )

    run = execute_run(run_id=run.pk, actor=manager)

    assert AssuranceFinding.objects.filter(
        last_detected_run=run, finding_type=FindingType.CUSTODY_MISMATCH
    ).exists()


@pytest.mark.django_db
def test_disposed_asset_with_open_work_order_reports_lifecycle_and_workflow(manager, asset_factory):
    from maintenance.models import MaintenanceType, WorkOrder

    asset = asset_factory(status=AssetStatus.DISPOSED)
    WorkOrder.objects.create(
        organization=manager.organization,
        work_order_number="ASR-WO-0001",
        asset=asset,
        maintenance_type=MaintenanceType.CORRECTIVE,
        description="Open after disposal for assurance test",
        requested_by=manager,
    )
    run = create_run(actor=manager, run_type=AssuranceRunType.OPERATIONAL)

    run = execute_run(run_id=run.pk, actor=manager)

    types = set(
        AssuranceFinding.objects.filter(last_detected_run=run).values_list(
            "finding_type", flat=True
        )
    )
    assert FindingType.LIFECYCLE_MISMATCH in types
    assert FindingType.OPEN_WORKFLOW in types


@pytest.mark.django_db
def test_completed_disposal_must_match_asset_lifecycle(manager, accountant, asset_factory):
    from datetime import date

    from disposals.models import Disposal, DisposalMethod, DisposalStatus

    asset = asset_factory()
    now = timezone.now() + timedelta(seconds=1)
    Disposal.objects.create(
        organization=manager.organization,
        asset=asset,
        disposal_date=date.today(),
        disposal_method=DisposalMethod.SALE,
        reason="Completed disposal test",
        currency="NGN",
        capitalized_cost_at_disposal=asset.purchase_cost,
        accumulated_depreciation_at_disposal=asset.accumulated_depreciation,
        carrying_amount=asset.current_book_value,
        gain_or_loss=Decimal("-1000.00"),
        status=DisposalStatus.COMPLETED,
        requested_by=manager,
        submitted_by=manager,
        submitted_at=now,
        approved_by=accountant,
        approved_at=now + timedelta(seconds=1),
        completed_at=now + timedelta(seconds=2),
        created_by=manager,
        updated_by=manager,
    )
    run = create_run(actor=manager, run_type=AssuranceRunType.FINANCIAL)

    run = execute_run(run_id=run.pk, actor=manager)

    finding = AssuranceFinding.objects.get(
        last_detected_run=run, finding_type=FindingType.DISPOSAL_STATUS_MISMATCH
    )
    assert finding.expected_value == AssetStatus.DISPOSED
    assert finding.observed_value == AssetStatus.ACTIVE


@pytest.mark.django_db
def test_invalid_cross_organization_run_record_rejected(manager, foreign_manager):
    run = AssuranceRun(
        organization=manager.organization,
        started_by=foreign_manager,
        run_type=AssuranceRunType.FULL,
    )
    with pytest.raises(ValidationError):
        run.full_clean()


@pytest.mark.django_db
def test_assurance_history_cannot_be_deleted_or_bulk_changed(manager, asset_factory):
    asset_factory(current_book_value=Decimal("900.00"))
    run = execute_run(
        run_id=create_run(actor=manager, run_type=AssuranceRunType.FULL).pk,
        actor=manager,
    )
    finding = AssuranceFinding.objects.filter(last_detected_run=run).first()

    with pytest.raises(ValidationError):
        run.delete()
    with pytest.raises(ValidationError):
        AssuranceRun.objects.filter(pk=run.pk).delete()
    with pytest.raises(ValidationError):
        AssuranceFinding.objects.filter(pk=finding.pk).update(description="rewritten")
    with pytest.raises(ValidationError):
        finding.occurrences.all().delete()
