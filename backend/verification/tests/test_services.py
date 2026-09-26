from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connections, transaction

from accounts.models import User
from assets.models import AssetCondition, AssetStatus
from audit.models import AuditLog
from verification.models import (
    CampaignScope,
    CampaignStatus,
    EvidenceType,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    PhysicalCondition,
    PhysicalVerification,
    VerificationResult,
)
from verification.selectors import campaigns_for_organization, expected_assets
from verification.services import (
    accept_exception,
    assign_exception,
    cancel_campaign,
    complete_campaign,
    create_campaign,
    create_evidence,
    create_manual_exception,
    create_verification,
    reconcile_missing_assets,
    reject_exception,
    resolve_exception,
    start_campaign,
    start_exception_review,
    update_campaign,
)


@pytest.mark.django_db
def test_campaign_scope_validation_lifecycle_and_org_isolation(
    campaign_factory, manager, department, foreign_department, other_organization
):
    campaign = campaign_factory(scope_type=CampaignScope.DEPARTMENT)
    assert campaign.status == CampaignStatus.DRAFT
    with pytest.raises(ValidationError, match="only a department"):
        campaign_factory(scope_type=CampaignScope.DEPARTMENT, department=None)
    with pytest.raises(ValidationError, match="organization"):
        campaign_factory(scope_type=CampaignScope.DEPARTMENT, department=foreign_department)
    opened = start_campaign(campaign_id=campaign.pk, actor=manager)
    assert opened.status == CampaignStatus.OPEN
    with pytest.raises(ValidationError, match="draft"):
        update_campaign(campaign_id=campaign.pk, actor=manager, changes={"name": "Changed"})
    completed = complete_campaign(campaign_id=campaign.pk, actor=manager)
    assert completed.status == CampaignStatus.COMPLETED
    with pytest.raises(ValidationError, match="can no longer be cancelled"):
        cancel_campaign(campaign_id=campaign.pk, actor=manager)
    foreign_manager = User.objects.create_user(
        "foreign@example.com",
        "secret-password",
        organization=other_organization,
        role="ASSET_MANAGER",
    )
    with pytest.raises(ValidationError, match="not found"):
        start_campaign(campaign_id=campaign.pk, actor=foreign_manager)


@pytest.mark.django_db
def test_campaign_progress_is_database_derived_and_disposed_assets_excluded(
    campaign_factory, manager, asset_factory, department, location
):
    expected = asset_factory()
    asset_factory(status=AssetStatus.DISPOSED, asset_tag="DISPOSED-1")
    asset_factory(status=AssetStatus.DRAFT, asset_tag="DRAFT-1")
    campaign = campaign_factory()
    start_campaign(campaign_id=campaign.pk, actor=manager)
    create_verification(
        actor=manager,
        campaign_id=campaign.pk,
        asset_id=expected.pk,
        observed_asset_tag=expected.asset_tag,
        observed_department=department,
        observed_location=location,
    )
    progress = campaigns_for_organization(manager.organization, manager).get(pk=campaign.pk)
    assert progress.expected_asset_count == 1
    assert progress.verified_asset_count == 1
    assert progress.unverified_asset_count == 0
    assert progress.verification_percentage == Decimal("100.00")
    assert expected_assets(campaign).count() == 1


@pytest.mark.django_db
def test_matching_observation_preserves_asset_and_custody_master_data(
    open_campaign, manager, asset_factory, department, location, employee
):
    from transfers.services import assign_asset

    asset = asset_factory()
    assignment = assign_asset(
        asset_id=asset.pk,
        actor=manager,
        assigned_to=employee,
    )
    authoritative = {
        "department_id": asset.department_id,
        "location_id": asset.location_id,
        "status": asset.status,
        "purchase_cost": asset.purchase_cost,
        "current_book_value": asset.current_book_value,
        "accumulated_depreciation": asset.accumulated_depreciation,
    }
    record = create_verification(
        actor=manager,
        campaign_id=open_campaign.pk,
        asset_id=asset.pk,
        observed_asset_tag=asset.asset_tag,
        observed_department=department,
        observed_location=location,
        observed_custodian=employee,
        observed_condition=PhysicalCondition.GOOD,
    )
    asset.refresh_from_db()
    assignment.refresh_from_db()
    assert record.result == VerificationResult.VERIFIED
    assert not record.exceptions.exists()
    assert {key: getattr(asset, key) for key in authoritative} == authoritative
    assert assignment.returned_at is None


@pytest.mark.django_db
def test_condition_reconciliation_compares_with_register_without_updating_asset(
    open_campaign, manager, asset_factory, department, location
):
    asset = asset_factory(condition=AssetCondition.GOOD)
    record = create_verification(
        actor=manager,
        campaign_id=open_campaign.pk,
        asset_id=asset.pk,
        observed_asset_tag=asset.asset_tag,
        observed_department=department,
        observed_location=location,
        observed_condition=PhysicalCondition.FAIR,
    )

    assert record.result == VerificationResult.CONDITION_MISMATCH
    assert record.exceptions.filter(exception_type=ExceptionType.CONDITION_MISMATCH).exists()
    asset.refresh_from_db()
    assert asset.condition == AssetCondition.GOOD


@pytest.mark.django_db
def test_reconciliation_generates_location_department_custody_tag_damage_and_lifecycle_exceptions(
    open_campaign, manager, asset_factory, other_department, other_location, employee
):
    from transfers.services import assign_asset

    asset = asset_factory()
    assign_asset(asset_id=asset.pk, actor=manager, assigned_to=employee)
    record = create_verification(
        actor=manager,
        campaign_id=open_campaign.pk,
        asset_id=asset.pk,
        observed_asset_tag="WRONG-TAG",
        observed_department=other_department,
        observed_location=other_location,
        observed_custodian=None,
        observed_condition=PhysicalCondition.DAMAGED,
    )
    assert record.result == VerificationResult.LOCATION_MISMATCH
    assert set(record.exceptions.values_list("exception_type", flat=True)) == {
        ExceptionType.TAG_MISMATCH,
        ExceptionType.LOCATION_MISMATCH,
        ExceptionType.DEPARTMENT_MISMATCH,
        ExceptionType.CUSTODY_MISMATCH,
        ExceptionType.DAMAGED_ASSET,
    }
    assert (
        record.exceptions.get(exception_type=ExceptionType.DAMAGED_ASSET).severity
        == ExceptionSeverity.HIGH
    )

    disposed_campaign = open_campaign.__class__.objects.get(pk=open_campaign.pk)
    disposed_asset = asset_factory(status=AssetStatus.DISPOSED, asset_tag="DISPOSED-OBS")
    # The asset belongs to the open campaign's organization-wide scope.
    lifecycle_record = create_verification(
        actor=manager,
        campaign_id=disposed_campaign.pk,
        asset_id=disposed_asset.pk,
        observed_asset_tag=disposed_asset.asset_tag,
        observed_department=disposed_asset.department,
        observed_location=disposed_asset.location,
        observed_condition=PhysicalCondition.CRITICAL,
    )
    assert lifecycle_record.exceptions.filter(
        exception_type=ExceptionType.LIFECYCLE_MISMATCH
    ).exists()
    assert (
        lifecycle_record.exceptions.get(exception_type=ExceptionType.DAMAGED_ASSET).severity
        == ExceptionSeverity.CRITICAL
    )


@pytest.mark.django_db
def test_unregistered_missing_tag_and_duplicate_tags_create_persistent_exceptions(
    open_campaign, manager, asset_factory, department, location
):
    unregistered = create_verification(
        actor=manager,
        campaign_id=open_campaign.pk,
        observed_asset_tag="FOUND-UNKNOWN",
        observed_description="Unregistered generator",
        observed_department=department,
        observed_location=location,
    )
    assert unregistered.result == VerificationResult.UNREGISTERED_ASSET
    assert unregistered.asset is None
    assert unregistered.exceptions.filter(exception_type=ExceptionType.UNREGISTERED_ASSET).exists()

    first = asset_factory(asset_tag="DUP-A")
    second = asset_factory(asset_tag="DUP-B")
    first_record = create_verification(
        actor=manager,
        campaign_id=open_campaign.pk,
        asset_id=first.pk,
        observed_asset_tag="DUP-A",
        observed_department=department,
        observed_location=location,
    )
    second_record = create_verification(
        actor=manager,
        campaign_id=open_campaign.pk,
        asset_id=second.pk,
        observed_asset_tag="DUP-A",
        observed_department=department,
        observed_location=location,
    )
    assert second_record.result == VerificationResult.DUPLICATE_TAG
    assert first_record.exceptions.filter(exception_type=ExceptionType.DUPLICATE_TAG).exists()
    assert second_record.exceptions.filter(exception_type=ExceptionType.DUPLICATE_TAG).exists()
    first_record.refresh_from_db()
    assert first_record.result == VerificationResult.DUPLICATE_TAG
    assert AuditLog.objects.filter(
        action="VERIFICATION_RESULT_RECONCILED", entity_id=str(first_record.pk)
    ).exists()

    first_record.result = VerificationResult.DAMAGED
    with pytest.raises(ValidationError, match="immutable"):
        first_record.save(update_fields=("result",))
    first_record.refresh_from_db()
    assert first_record.result == VerificationResult.DUPLICATE_TAG

    other_campaign = create_campaign(
        actor=manager,
        name="Missing campaign",
        scope_type=CampaignScope.ORGANIZATION,
        start_date=manager.created_at.date(),
    )
    start_campaign(campaign_id=other_campaign.pk, actor=manager)
    missing_asset = asset_factory(asset_tag="MISSING-1")
    created_count = reconcile_missing_assets(campaign_id=other_campaign.pk, actor=manager)
    missing = PhysicalVerification.objects.get(campaign=other_campaign, asset=missing_asset)
    assert created_count == 3
    assert missing.result == VerificationResult.ASSET_NOT_FOUND
    assert missing.exceptions.filter(exception_type=ExceptionType.ASSET_NOT_FOUND).exists()


@pytest.mark.django_db
def test_duplicate_asset_verification_is_database_unique_and_service_rejects_repeat(
    open_campaign, manager, asset_factory, department, location
):
    asset = asset_factory()
    data = {
        "actor": manager,
        "campaign_id": open_campaign.pk,
        "asset_id": asset.pk,
        "observed_asset_tag": asset.asset_tag,
        "observed_department": department,
        "observed_location": location,
    }
    create_verification(**data)
    with pytest.raises(ValidationError, match="already has a verification"):
        create_verification(**data)
    with pytest.raises(IntegrityError), transaction.atomic():
        PhysicalVerification.objects.create(
            organization=manager.organization,
            campaign=open_campaign,
            asset=asset,
            verified_by=manager,
            result=VerificationResult.VERIFIED,
            observed_department=department,
            observed_location=location,
            observed_asset_tag=asset.asset_tag,
        )


@pytest.mark.django_db
def test_department_manager_can_verify_only_within_department(
    campaign_factory, department_manager, asset_factory, department, other_department, location
):
    campaign = campaign_factory(scope_type=CampaignScope.DEPARTMENT)
    start_campaign(campaign_id=campaign.pk, actor=campaign.created_by)
    in_scope = asset_factory()
    result = create_verification(
        actor=department_manager,
        campaign_id=campaign.pk,
        asset_id=in_scope.pk,
        observed_asset_tag=in_scope.asset_tag,
        observed_department=department,
        observed_location=location,
    )
    assert result.asset_id == in_scope.pk
    outside = asset_factory(asset_tag="OTHER-DEP", department=other_department)
    with pytest.raises(ValidationError, match="outside"):
        create_verification(
            actor=department_manager,
            campaign_id=campaign.pk,
            asset_id=outside.pk,
            observed_asset_tag=outside.asset_tag,
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "scope_type,scope_field",
    [(CampaignScope.DEPARTMENT, "department"), (CampaignScope.LOCATION, "location")],
)
def test_scoped_campaign_progress_counts_only_matching_expected_assets(
    campaign_factory, manager, asset_factory, department, location, scope_type, scope_field
):
    asset_factory()
    other = asset_factory(asset_tag="OUTSIDE-SCOPE", **{scope_field: None})
    selected = department if scope_type == CampaignScope.DEPARTMENT else location
    campaign = campaign_factory(scope_type=scope_type)
    # The default fixture asset is in scope, while the second is intentionally outside it.
    start_campaign(campaign_id=campaign.pk, actor=manager)
    progress = campaigns_for_organization(manager.organization, manager).get(pk=campaign.pk)
    assert progress.expected_asset_count == 1
    assert other.pk not in expected_assets(campaign).values_list("pk", flat=True)
    assert selected.organization_id == manager.organization_id


@pytest.mark.django_db
def test_exception_lifecycle_assignment_resolution_and_history_preserved(
    open_campaign,
    manager,
    admin_user,
    employee,
    asset_factory,
    other_location,
    department,
    location,
):
    asset = asset_factory()
    verification = create_verification(
        actor=manager,
        campaign_id=open_campaign.pk,
        asset_id=asset.pk,
        observed_asset_tag=asset.asset_tag,
        observed_department=department,
        observed_location=other_location,
    )
    exception = verification.exceptions.get(exception_type=ExceptionType.LOCATION_MISMATCH)
    original_observation = (verification.observed_location_id, verification.result)
    assigned = assign_exception(exception_id=exception.pk, actor=manager, assigned_to=employee)
    assert assigned.assigned_to_id == employee.pk
    reviewed = start_exception_review(exception_id=exception.pk, actor=manager)
    assert reviewed.status == ExceptionStatus.UNDER_REVIEW
    resolved = resolve_exception(
        exception_id=exception.pk,
        actor=manager,
        resolution_notes="Transfer completed using the transfer workflow.",
        resolution_reference="TRF-001",
    )
    verification.refresh_from_db()
    assert resolved.status == ExceptionStatus.RESOLVED
    assert resolved.resolved_by_id == manager.pk
    assert resolved.resolution_reference == "TRF-001"
    assert (verification.observed_location_id, verification.result) == original_observation
    with pytest.raises(ValidationError, match="under review"):
        accept_exception(exception_id=exception.pk, actor=admin_user, resolution_notes="Duplicate")
    assert AuditLog.objects.filter(action="VERIFICATION_EXCEPTION_RESOLVED").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "service,status",
    [(accept_exception, ExceptionStatus.ACCEPTED), (reject_exception, ExceptionStatus.REJECTED)],
)
def test_exception_accept_and_reject(
    service, open_campaign, manager, asset_factory, department, location, status
):
    asset = asset_factory()
    verification = create_verification(
        actor=manager,
        campaign_id=open_campaign.pk,
        asset_id=asset.pk,
        observed_asset_tag="",
        observed_department=department,
        observed_location=location,
    )
    exception = verification.exceptions.get(exception_type=ExceptionType.TAG_MISSING)
    start_exception_review(exception_id=exception.pk, actor=manager)
    result = service(exception_id=exception.pk, actor=manager, resolution_notes="Reviewed")
    assert result.status == status
    assert result.resolved_at and result.resolved_by_id == manager.pk


@pytest.mark.django_db
def test_manual_other_exception_preserves_physical_observation(
    open_campaign, manager, asset_factory, department, location
):
    asset = asset_factory()
    verification = create_verification(
        actor=manager,
        campaign_id=open_campaign.pk,
        asset_id=asset.pk,
        observed_asset_tag=asset.asset_tag,
        observed_department=department,
        observed_location=location,
    )
    exception = create_manual_exception(
        actor=manager,
        verification_id=verification.pk,
        description="Reviewer identified an unmodeled issue.",
    )
    verification.refresh_from_db()
    assert exception.exception_type == ExceptionType.OTHER
    assert verification.result == VerificationResult.OTHER_EXCEPTION
    assert verification.observed_asset_tag == asset.asset_tag
    assert verification.observed_location_id == location.pk
    assert AuditLog.objects.filter(
        action="VERIFICATION_RESULT_RECONCILED", entity_id=str(verification.pk)
    ).exists()


@pytest.mark.django_db
def test_evidence_metadata_and_cross_organization_relationships(
    open_campaign, manager, other_organization, foreign_manager, asset_factory, department, location
):
    asset = asset_factory()
    verification = create_verification(
        actor=manager,
        campaign_id=open_campaign.pk,
        asset_id=asset.pk,
        observed_asset_tag="",
        observed_department=department,
        observed_location=location,
    )
    exception = verification.exceptions.get(exception_type=ExceptionType.TAG_MISSING)
    evidence = create_evidence(
        actor=manager,
        verification_id=verification.pk,
        exception=exception,
        evidence_type=EvidenceType.PHOTO,
        file_name="front.jpg",
        content_type="image/jpeg",
        storage_key="metadata-only/asset/front.jpg",
        description="Asset tag and front view.",
    )
    assert evidence.storage_key == "metadata-only/asset/front.jpg"
    assert not hasattr(evidence, "file")
    with pytest.raises(ValidationError, match="not found"):
        create_evidence(
            actor=foreign_manager,
            verification_id=verification.pk,
            evidence_type=EvidenceType.NOTE,
            description="Cross-organization evidence",
        )


@pytest.mark.django_db
def test_audit_failure_rolls_back_verification_and_generated_exceptions(
    open_campaign, manager, asset_factory, department, other_location
):
    from unittest.mock import patch

    asset = asset_factory()
    with patch("verification.services.record_event", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError):
            create_verification(
                actor=manager,
                campaign_id=open_campaign.pk,
                asset_id=asset.pk,
                observed_asset_tag=asset.asset_tag,
                observed_department=department,
                observed_location=other_location,
            )
    assert not PhysicalVerification.objects.filter(campaign=open_campaign, asset=asset).exists()
    assert not open_campaign.exceptions.exists()
    open_campaign.refresh_from_db()
    assert open_campaign.status == CampaignStatus.OPEN


@pytest.mark.django_db(transaction=True)
def test_concurrent_verification_for_same_asset_is_serialized_and_unique(
    open_campaign, manager, asset_factory, department, location
):
    from accounts.models import User

    asset = asset_factory()
    campaign_id, asset_id, actor_id = open_campaign.pk, asset.pk, manager.pk
    barrier = Barrier(2)

    def run():
        close_old_connections()
        try:
            actor = User.objects.get(pk=actor_id)
            barrier.wait(timeout=10)
            try:
                create_verification(
                    actor=actor,
                    campaign_id=campaign_id,
                    asset_id=asset_id,
                    observed_asset_tag="AST-VER-00001",
                    observed_department=department,
                    observed_location=location,
                )
                return "created"
            except ValidationError:
                return "rejected"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result(timeout=30) for future in (executor.submit(run), executor.submit(run))
        ]
    assert sorted(results) == ["created", "rejected"]
    assert PhysicalVerification.objects.filter(campaign=open_campaign, asset=asset).count() == 1
