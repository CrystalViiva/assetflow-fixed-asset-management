"""Transactional campaign, observation, reconciliation, and exception operations."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import UserRole
from assets.models import Asset, AssetStatus
from audit.services import record_event
from transfers.models import AssetAssignment
from verification.models import (
    CampaignScope,
    CampaignStatus,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    PhysicalCondition,
    PhysicalVerification,
    VerificationCampaign,
    VerificationEvidence,
    VerificationException,
    VerificationResult,
)
from verification.selectors import expected_assets


def _organization(actor):
    if not getattr(actor, "organization_id", None):
        raise ValidationError({"organization": "The user must belong to an organization."})
    return actor.organization


def _audit(
    *,
    organization,
    actor,
    action,
    entity_type,
    entity_id,
    metadata=None,
    changes=None,
    ip_address=None,
):
    return record_event(
        organization=organization,
        user=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
        changes=changes or {},
        ip_address=ip_address,
    )


def _locked_campaign(campaign_id, organization):
    try:
        return VerificationCampaign.objects.select_for_update(of=("self",)).get(
            pk=campaign_id, organization=organization
        )
    except VerificationCampaign.DoesNotExist as exc:
        raise ValidationError({"campaign": "Campaign was not found in your organization."}) from exc


def _locked_exception(exception_id, organization):
    try:
        return VerificationException.objects.select_for_update(of=("self",)).get(
            pk=exception_id, organization=organization
        )
    except VerificationException.DoesNotExist as exc:
        raise ValidationError(
            {"exception": "Exception was not found in your organization."}
        ) from exc


def _same_org(value, organization, field):
    if value is not None and value.organization_id != organization.pk:
        raise ValidationError({field: "This reference must belong to your organization."})


def _campaign_scope(campaign, *, department_id=None, location_id=None):
    if campaign.scope_type == CampaignScope.DEPARTMENT:
        if department_id != campaign.department_id:
            raise ValidationError(
                {"department": "Observation is outside the campaign department scope."}
            )
    elif campaign.scope_type == CampaignScope.LOCATION:
        if location_id != campaign.location_id:
            raise ValidationError(
                {"location": "Observation is outside the campaign location scope."}
            )


def create_campaign(
    *,
    actor,
    name,
    scope_type,
    start_date,
    department=None,
    location=None,
    description="",
    due_date=None,
    ip_address=None,
):
    organization = _organization(actor)
    _same_org(department, organization, "department")
    _same_org(location, organization, "location")
    if actor.role == UserRole.DEPARTMENT_MANAGER:
        raise ValidationError(
            {"permission": "Department managers cannot create verification campaigns."}
        )
    with transaction.atomic():
        campaign = VerificationCampaign(
            organization=organization,
            name=name,
            description=description,
            scope_type=scope_type,
            department=department,
            location=location,
            start_date=start_date,
            due_date=due_date,
            created_by=actor,
            updated_by=actor,
        )
        campaign.full_clean()
        campaign.save()
        _audit(
            organization=organization,
            actor=actor,
            action="VERIFICATION_CAMPAIGN_CREATED",
            entity_type="VERIFICATION_CAMPAIGN",
            entity_id=campaign.pk,
            metadata={"scope_type": campaign.scope_type},
            ip_address=ip_address,
        )
    return campaign


def update_campaign(*, campaign_id, actor, changes, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        campaign = _locked_campaign(campaign_id, organization)
        if campaign.status != CampaignStatus.DRAFT:
            raise ValidationError({"status": "Only draft campaigns can be edited."})
        allowed = {
            "name",
            "description",
            "scope_type",
            "department",
            "location",
            "start_date",
            "due_date",
        }
        if set(changes) - allowed:
            raise ValidationError(
                {"fields": "Campaign status and audit fields are workflow-controlled."}
            )
        for field, value in changes.items():
            _same_org(value, organization, field)
            setattr(campaign, field, value)
        campaign.updated_by = actor
        campaign.full_clean()
        campaign.save()
        _audit(
            organization=organization,
            actor=actor,
            action="VERIFICATION_CAMPAIGN_UPDATED",
            entity_type="VERIFICATION_CAMPAIGN",
            entity_id=campaign.pk,
            metadata={"fields": sorted(changes)},
            ip_address=ip_address,
        )
    return campaign


def start_campaign(*, campaign_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        campaign = _locked_campaign(campaign_id, organization)
        if campaign.status != CampaignStatus.DRAFT:
            raise ValidationError({"status": "Only a draft campaign can be opened."})
        campaign.status = CampaignStatus.OPEN
        campaign.opened_at = timezone.now()
        campaign.updated_by = actor
        campaign.full_clean()
        campaign.save(update_fields=("status", "opened_at", "updated_by", "updated_at"))
        _audit(
            organization=organization,
            actor=actor,
            action="VERIFICATION_CAMPAIGN_STARTED",
            entity_type="VERIFICATION_CAMPAIGN",
            entity_id=campaign.pk,
            changes={"status": {"from": CampaignStatus.DRAFT, "to": CampaignStatus.OPEN}},
            ip_address=ip_address,
        )
    return campaign


def complete_campaign(*, campaign_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        campaign = _locked_campaign(campaign_id, organization)
        if campaign.status not in (CampaignStatus.OPEN, CampaignStatus.IN_PROGRESS):
            raise ValidationError({"status": "Only open campaigns can be completed."})
        before = campaign.status
        campaign.status = CampaignStatus.COMPLETED
        campaign.completed_at = timezone.now()
        campaign.updated_by = actor
        campaign.full_clean()
        campaign.save(update_fields=("status", "completed_at", "updated_by", "updated_at"))
        _audit(
            organization=organization,
            actor=actor,
            action="VERIFICATION_CAMPAIGN_COMPLETED",
            entity_type="VERIFICATION_CAMPAIGN",
            entity_id=campaign.pk,
            changes={"status": {"from": before, "to": campaign.status}},
            ip_address=ip_address,
        )
    return campaign


def cancel_campaign(*, campaign_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        campaign = _locked_campaign(campaign_id, organization)
        if campaign.status not in (
            CampaignStatus.DRAFT,
            CampaignStatus.OPEN,
            CampaignStatus.IN_PROGRESS,
        ):
            raise ValidationError({"status": "This campaign can no longer be cancelled."})
        before = campaign.status
        campaign.status = CampaignStatus.CANCELLED
        campaign.updated_by = actor
        campaign.full_clean()
        campaign.save(update_fields=("status", "updated_by", "updated_at"))
        _audit(
            organization=organization,
            actor=actor,
            action="VERIFICATION_CAMPAIGN_CANCELLED",
            entity_type="VERIFICATION_CAMPAIGN",
            entity_id=campaign.pk,
            changes={"status": {"from": before, "to": campaign.status}},
            ip_address=ip_address,
        )
    return campaign


def _exception(*, verification, exception_type, description, severity, actor, ip_address=None):
    exception = VerificationException(
        organization=verification.organization,
        campaign=verification.campaign,
        verification=verification,
        asset=verification.asset,
        exception_type=exception_type,
        severity=severity,
        description=description,
    )
    exception.full_clean()
    exception.save()
    _audit(
        organization=verification.organization,
        actor=actor,
        action="VERIFICATION_EXCEPTION_CREATED",
        entity_type="VERIFICATION_EXCEPTION",
        entity_id=exception.pk,
        metadata={"verification_id": str(verification.pk), "type": exception_type},
        ip_address=ip_address,
    )
    return exception


def _update_verification_result(verification, *, result, actor, ip_address=None):
    """Update the derived summary explicitly and retain an audit trail for the change."""
    before = verification.result
    if before == result:
        return
    now = timezone.now()
    PhysicalVerification.objects.filter(pk=verification.pk).update(result=result, updated_at=now)
    verification.result = result
    verification.updated_at = now
    _audit(
        organization=verification.organization,
        actor=actor,
        action="VERIFICATION_RESULT_RECONCILED",
        entity_type="PHYSICAL_VERIFICATION",
        entity_id=verification.pk,
        changes={"result": {"from": before, "to": result}},
        ip_address=ip_address,
    )


def _reconcile(verification, *, actor, ip_address=None):
    asset = verification.asset
    detected = []
    if asset is None:
        detected.append(
            (
                ExceptionType.UNREGISTERED_ASSET,
                ExceptionSeverity.HIGH,
                "Observed physical item has no matching asset master record.",
            )
        )
        if not verification.observed_asset_tag:
            detected.append(
                (
                    ExceptionType.TAG_MISSING,
                    ExceptionSeverity.MEDIUM,
                    "Observed unregistered item has no asset tag.",
                )
            )
    else:
        if not verification.observed_asset_tag:
            detected.append(
                (
                    ExceptionType.TAG_MISSING,
                    ExceptionSeverity.MEDIUM,
                    "The asset tag was not observed.",
                )
            )
        elif verification.observed_asset_tag.strip() != asset.asset_tag:
            detected.append(
                (
                    ExceptionType.TAG_MISMATCH,
                    ExceptionSeverity.HIGH,
                    "Observed tag "
                    f"{verification.observed_asset_tag!r} differs from registered tag "
                    f"{asset.asset_tag!r}.",
                )
            )
        if verification.observed_location_id != asset.location_id:
            detected.append(
                (
                    ExceptionType.LOCATION_MISMATCH,
                    ExceptionSeverity.MEDIUM,
                    "Observed location differs from the asset register.",
                )
            )
        if verification.observed_department_id != asset.department_id:
            detected.append(
                (
                    ExceptionType.DEPARTMENT_MISMATCH,
                    ExceptionSeverity.MEDIUM,
                    "Observed department differs from the asset register.",
                )
            )
        authoritative_custodian = (
            AssetAssignment.objects.filter(asset_id=asset.pk, returned_at__isnull=True)
            .values_list("assigned_to_id", flat=True)
            .first()
        )
        if authoritative_custodian != verification.observed_custodian_id:
            detected.append(
                (
                    ExceptionType.CUSTODY_MISMATCH,
                    ExceptionSeverity.HIGH,
                    "Observed custodian differs from the active assignment record.",
                )
            )
        if asset.status in (
            AssetStatus.DISPOSED,
            AssetStatus.DRAFT,
            AssetStatus.PENDING_CAPITALIZATION,
        ):
            detected.append(
                (
                    ExceptionType.LIFECYCLE_MISMATCH,
                    ExceptionSeverity.CRITICAL,
                    f"Physical observation conflicts with asset lifecycle status {asset.status}.",
                )
            )
        if (
            verification.observed_condition != PhysicalCondition.UNKNOWN
            and asset.condition != PhysicalCondition.UNKNOWN
            and verification.observed_condition != asset.condition
        ):
            detected.append(
                (
                    ExceptionType.CONDITION_MISMATCH,
                    ExceptionSeverity.HIGH
                    if verification.observed_condition
                    in (PhysicalCondition.DAMAGED, PhysicalCondition.CRITICAL)
                    else ExceptionSeverity.MEDIUM,
                    "Observed condition differs from the asset register.",
                )
            )
    if verification.observed_condition == PhysicalCondition.DAMAGED:
            detected.append(
            (
                ExceptionType.DAMAGED_ASSET,
                ExceptionSeverity.HIGH,
                "The asset was observed in damaged condition.",
            )
        )
    elif verification.observed_condition == PhysicalCondition.CRITICAL:
        detected.append(
            (
                ExceptionType.DAMAGED_ASSET,
                ExceptionSeverity.CRITICAL,
                "The asset was observed in critical condition.",
            )
        )

    tag = verification.observed_asset_tag.strip()
    duplicate_ids = []
    if tag:
        duplicates = PhysicalVerification.objects.filter(
            campaign=verification.campaign, observed_asset_tag__iexact=tag
        ).exclude(pk=verification.pk)
        duplicate_ids = list(duplicates.values_list("pk", flat=True))
        if duplicate_ids:
            detected.append(
                (
                    ExceptionType.DUPLICATE_TAG,
                    ExceptionSeverity.CRITICAL,
                    f"Observed tag {tag!r} appears more than once in this campaign.",
                )
            )

    result_priority = (
        (ExceptionType.UNREGISTERED_ASSET, VerificationResult.UNREGISTERED_ASSET),
        (ExceptionType.DUPLICATE_TAG, VerificationResult.DUPLICATE_TAG),
        (ExceptionType.ASSET_NOT_FOUND, VerificationResult.ASSET_NOT_FOUND),
        (ExceptionType.TAG_MISSING, VerificationResult.TAG_MISSING),
        (ExceptionType.CONDITION_MISMATCH, VerificationResult.CONDITION_MISMATCH),
        (ExceptionType.LOCATION_MISMATCH, VerificationResult.LOCATION_MISMATCH),
        (ExceptionType.CUSTODY_MISMATCH, VerificationResult.CUSTODY_MISMATCH),
        (ExceptionType.DAMAGED_ASSET, VerificationResult.DAMAGED),
    )
    result = next(
        (
            value
            for exception_type, value in result_priority
            if any(item[0] == exception_type for item in detected)
        ),
        None,
    )
    if result is None:
        result = VerificationResult.OTHER_EXCEPTION if detected else VerificationResult.VERIFIED
    _update_verification_result(
        verification, result=result, actor=actor, ip_address=ip_address
    )
    created = []
    for exception_type, severity, description in detected:
        created.append(
            _exception(
                verification=verification,
                exception_type=exception_type,
                description=description,
                severity=severity,
                actor=actor,
                ip_address=ip_address,
            )
        )

    # Duplicate evidence applies to both records. Preserve the earlier physical observation
    # and attach its own exception rather than rewriting it or its result.
    for duplicate_id in duplicate_ids:
        earlier = PhysicalVerification.objects.select_for_update().get(pk=duplicate_id)
        _update_verification_result(
            earlier,
            result=VerificationResult.DUPLICATE_TAG,
            actor=actor,
            ip_address=ip_address,
        )
        if not earlier.exceptions.filter(exception_type=ExceptionType.DUPLICATE_TAG).exists():
            _exception(
                verification=earlier,
                exception_type=ExceptionType.DUPLICATE_TAG,
                description=(
                    f"Observed tag {tag!r} also appears on another verification in this campaign."
                ),
                severity=ExceptionSeverity.CRITICAL,
                actor=actor,
                ip_address=ip_address,
            )
    return created


def create_verification(
    *,
    actor,
    campaign_id,
    asset_id=None,
    observed_asset_tag="",
    observed_description="",
    observed_location=None,
    observed_department=None,
    observed_custodian=None,
    observed_condition=PhysicalCondition.UNKNOWN,
    notes="",
    ip_address=None,
):
    organization = _organization(actor)
    for field, value in (
        ("observed_location", observed_location),
        ("observed_department", observed_department),
        ("observed_custodian", observed_custodian),
    ):
        _same_org(value, organization, field)
    if actor.role == UserRole.DEPARTMENT_MANAGER and not actor.department_id:
        raise ValidationError({"department": "A department manager must have a department."})
    with transaction.atomic():
        campaign = _locked_campaign(campaign_id, organization)
        if campaign.status not in (CampaignStatus.OPEN, CampaignStatus.IN_PROGRESS):
            raise ValidationError(
                {"campaign": "Only open campaigns accept physical verifications."}
            )
        if actor.role == UserRole.DEPARTMENT_MANAGER and (
            campaign.scope_type != CampaignScope.DEPARTMENT
            or campaign.department_id != actor.department_id
        ):
            raise ValidationError({"campaign": "Campaign is outside your department scope."})
        asset = None
        if asset_id:
            try:
                asset = Asset.objects.select_for_update(of=("self",)).get(
                    pk=asset_id, organization=organization
                )
            except Asset.DoesNotExist as exc:
                raise ValidationError(
                    {"asset": "Asset was not found in your organization."}
                ) from exc
            _campaign_scope(
                campaign, department_id=asset.department_id, location_id=asset.location_id
            )
            if PhysicalVerification.objects.filter(campaign=campaign, asset=asset).exists():
                raise ValidationError(
                    {"asset": "This asset already has a verification in this campaign."}
                )
        else:
            if campaign.scope_type == CampaignScope.DEPARTMENT and observed_department is None:
                observed_department = campaign.department
            if campaign.scope_type == CampaignScope.LOCATION and observed_location is None:
                observed_location = campaign.location
            _campaign_scope(
                campaign,
                department_id=getattr(observed_department, "pk", None),
                location_id=getattr(observed_location, "pk", None),
            )
        if actor.role == UserRole.DEPARTMENT_MANAGER:
            target_department_id = (
                asset.department_id if asset else getattr(observed_department, "pk", None)
            )
            if target_department_id != actor.department_id:
                raise ValidationError({"asset": "Verification is outside your department scope."})

        verification = PhysicalVerification(
            organization=organization,
            campaign=campaign,
            asset=asset,
            verified_by=actor,
            result=VerificationResult.UNREGISTERED_ASSET
            if asset is None
            else VerificationResult.VERIFIED,
            observed_location=observed_location,
            observed_department=observed_department,
            observed_custodian=observed_custodian,
            observed_condition=observed_condition,
            observed_asset_tag=observed_asset_tag.strip(),
            observed_description=observed_description,
            notes=notes,
        )
        verification.full_clean()
        try:
            verification.save()
        except IntegrityError as exc:
            raise ValidationError(
                {"asset": "This asset already has a verification in this campaign."}
            ) from exc
        if campaign.status == CampaignStatus.OPEN:
            campaign.status = CampaignStatus.IN_PROGRESS
            campaign.updated_by = actor
            campaign.save(update_fields=("status", "updated_by", "updated_at"))
            _audit(
                organization=organization,
                actor=actor,
                action="VERIFICATION_CAMPAIGN_IN_PROGRESS",
                entity_type="VERIFICATION_CAMPAIGN",
                entity_id=campaign.pk,
                changes={"status": {"from": CampaignStatus.OPEN, "to": CampaignStatus.IN_PROGRESS}},
                ip_address=ip_address,
            )
        exceptions = _reconcile(verification, actor=actor, ip_address=ip_address)
        _audit(
            organization=organization,
            actor=actor,
            action="VERIFICATION_CREATED",
            entity_type="PHYSICAL_VERIFICATION",
            entity_id=verification.pk,
            metadata={
                "asset_id": str(asset.pk) if asset else None,
                "result": verification.result,
                "exception_count": len(exceptions),
            },
            ip_address=ip_address,
        )
    return verification


def create_manual_exception(
    *, actor, verification_id, description, severity=ExceptionSeverity.MEDIUM, ip_address=None
):
    """Record a reviewer-raised OTHER issue without editing the observed facts."""
    organization = _organization(actor)
    with transaction.atomic():
        campaign_id = (
            PhysicalVerification.objects.filter(pk=verification_id, organization=organization)
            .values_list("campaign_id", flat=True)
            .first()
        )
        if campaign_id is None:
            raise ValidationError(
                {"verification": "Verification was not found in your organization."}
            )
        campaign = _locked_campaign(campaign_id, organization)
        try:
            verification = (
                PhysicalVerification.objects.select_for_update(of=("self",))
                .select_related("campaign", "asset")
                .get(pk=verification_id, organization=organization)
            )
        except PhysicalVerification.DoesNotExist as exc:
            raise ValidationError(
                {"verification": "Verification was not found in your organization."}
            ) from exc
        if campaign.status not in (CampaignStatus.OPEN, CampaignStatus.IN_PROGRESS):
            raise ValidationError({"campaign": "Manual exceptions require an open campaign."})
        if VerificationException.objects.filter(
            verification=verification, exception_type=ExceptionType.OTHER
        ).exists():
            raise ValidationError({"exception_type": "A manual OTHER exception already exists."})
        exception = _exception(
            verification=verification,
            exception_type=ExceptionType.OTHER,
            description=description,
            severity=severity,
            actor=actor,
            ip_address=ip_address,
        )
        if verification.result == VerificationResult.VERIFIED:
            _update_verification_result(
                verification,
                result=VerificationResult.OTHER_EXCEPTION,
                actor=actor,
                ip_address=ip_address,
            )
    return exception


def reconcile_missing_assets(*, campaign_id, actor, ip_address=None):
    """Record expected assets not physically found, without altering their master records."""
    organization = _organization(actor)
    created = 0
    with transaction.atomic():
        campaign = _locked_campaign(campaign_id, organization)
        if campaign.status not in (CampaignStatus.OPEN, CampaignStatus.IN_PROGRESS):
            raise ValidationError({"campaign": "Only open campaigns can reconcile missing assets."})
        already_verified = PhysicalVerification.objects.filter(
            campaign=campaign, asset_id__isnull=False
        ).values("asset_id")
        missing = (
            expected_assets(campaign)
            .exclude(pk__in=already_verified)
            .select_related("department", "location")
        )
        for asset in missing.iterator(chunk_size=500):
            verification = PhysicalVerification(
                organization=organization,
                campaign=campaign,
                asset=asset,
                verified_by=actor,
                result=VerificationResult.ASSET_NOT_FOUND,
                observed_asset_tag="",
                observed_condition=PhysicalCondition.UNKNOWN,
                notes="Expected asset was not located during campaign reconciliation.",
            )
            verification.full_clean()
            verification.save()
            _exception(
                verification=verification,
                exception_type=ExceptionType.ASSET_NOT_FOUND,
                description="Expected asset was not physically located in the campaign scope.",
                severity=ExceptionSeverity.HIGH,
                actor=actor,
                ip_address=ip_address,
            )
            _audit(
                organization=organization,
                actor=actor,
                action="VERIFICATION_CREATED",
                entity_type="PHYSICAL_VERIFICATION",
                entity_id=verification.pk,
                metadata={"asset_id": str(asset.pk), "result": VerificationResult.ASSET_NOT_FOUND},
                ip_address=ip_address,
            )
            created += 1
    return created


def _set_exception_resolution(
    exception, *, actor, status, notes, reference, action, ip_address=None
):
    exception.status = status
    exception.resolution_notes = notes
    exception.resolution_reference = reference
    exception.resolved_by = actor
    exception.resolved_at = timezone.now()
    exception.save(
        update_fields=(
            "status",
            "resolution_notes",
            "resolution_reference",
            "resolved_by",
            "resolved_at",
            "updated_at",
        )
    )
    _audit(
        organization=exception.organization,
        actor=actor,
        action=action,
        entity_type="VERIFICATION_EXCEPTION",
        entity_id=exception.pk,
        changes={"status": {"from": ExceptionStatus.UNDER_REVIEW, "to": status}},
        metadata={"resolution_reference": reference},
        ip_address=ip_address,
    )
    return exception


def assign_exception(*, exception_id, actor, assigned_to, ip_address=None):
    organization = _organization(actor)
    _same_org(assigned_to, organization, "assigned_to")
    with transaction.atomic():
        exception = _locked_exception(exception_id, organization)
        if exception.status not in (ExceptionStatus.OPEN, ExceptionStatus.UNDER_REVIEW):
            raise ValidationError({"status": "Only active exceptions can be assigned."})
        before = exception.assigned_to_id
        exception.assigned_to = assigned_to
        exception.assigned_at = timezone.now()
        exception.save(update_fields=("assigned_to", "assigned_at", "updated_at"))
        _audit(
            organization=organization,
            actor=actor,
            action="VERIFICATION_EXCEPTION_ASSIGNED",
            entity_type="VERIFICATION_EXCEPTION",
            entity_id=exception.pk,
            changes={
                "assigned_to": {"from": str(before) if before else None, "to": str(assigned_to.pk)}
            },
            ip_address=ip_address,
        )
    return exception


def start_exception_review(*, exception_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        exception = _locked_exception(exception_id, organization)
        if exception.status != ExceptionStatus.OPEN:
            raise ValidationError({"status": "Only open exceptions can enter review."})
        exception.status = ExceptionStatus.UNDER_REVIEW
        exception.started_at = timezone.now()
        exception.save(update_fields=("status", "started_at", "updated_at"))
        _audit(
            organization=organization,
            actor=actor,
            action="VERIFICATION_EXCEPTION_REVIEW_STARTED",
            entity_type="VERIFICATION_EXCEPTION",
            entity_id=exception.pk,
            changes={"status": {"from": ExceptionStatus.OPEN, "to": ExceptionStatus.UNDER_REVIEW}},
            ip_address=ip_address,
        )
    return exception


def resolve_exception(
    *, exception_id, actor, resolution_notes, resolution_reference="", ip_address=None
):
    return _finish_exception(
        exception_id=exception_id,
        actor=actor,
        status=ExceptionStatus.RESOLVED,
        resolution_notes=resolution_notes,
        resolution_reference=resolution_reference,
        action="VERIFICATION_EXCEPTION_RESOLVED",
        ip_address=ip_address,
    )


def accept_exception(
    *, exception_id, actor, resolution_notes, resolution_reference="", ip_address=None
):
    return _finish_exception(
        exception_id=exception_id,
        actor=actor,
        status=ExceptionStatus.ACCEPTED,
        resolution_notes=resolution_notes,
        resolution_reference=resolution_reference,
        action="VERIFICATION_EXCEPTION_ACCEPTED",
        ip_address=ip_address,
    )


def reject_exception(
    *, exception_id, actor, resolution_notes, resolution_reference="", ip_address=None
):
    return _finish_exception(
        exception_id=exception_id,
        actor=actor,
        status=ExceptionStatus.REJECTED,
        resolution_notes=resolution_notes,
        resolution_reference=resolution_reference,
        action="VERIFICATION_EXCEPTION_REJECTED",
        ip_address=ip_address,
    )


def _finish_exception(
    *, exception_id, actor, status, resolution_notes, resolution_reference, action, ip_address
):
    organization = _organization(actor)
    with transaction.atomic():
        exception = _locked_exception(exception_id, organization)
        if exception.status != ExceptionStatus.UNDER_REVIEW:
            raise ValidationError({"status": "Only exceptions under review can be closed."})
        return _set_exception_resolution(
            exception,
            actor=actor,
            status=status,
            notes=resolution_notes,
            reference=resolution_reference,
            action=action,
            ip_address=ip_address,
        )


def create_evidence(
    *,
    actor,
    verification_id,
    evidence_type,
    exception=None,
    file_name="",
    content_type="",
    storage_key="",
    external_reference="",
    captured_at=None,
    description="",
    ip_address=None,
):
    organization = _organization(actor)
    with transaction.atomic():
        try:
            verification = PhysicalVerification.objects.select_for_update(of=("self",)).get(
                pk=verification_id, organization=organization
            )
        except PhysicalVerification.DoesNotExist as exc:
            raise ValidationError(
                {"verification": "Verification was not found in your organization."}
            ) from exc
        if exception and (
            exception.organization_id != organization.pk
            or exception.verification_id != verification.pk
        ):
            raise ValidationError(
                {"exception": "Exception must belong to this verification and organization."}
            )
        evidence = VerificationEvidence(
            organization=organization,
            verification=verification,
            exception=exception,
            evidence_type=evidence_type,
            file_name=file_name,
            content_type=content_type,
            storage_key=storage_key,
            external_reference=external_reference,
            captured_at=captured_at or timezone.now(),
            captured_by=actor,
            description=description,
        )
        evidence.full_clean()
        evidence.save()
        _audit(
            organization=organization,
            actor=actor,
            action="VERIFICATION_EVIDENCE_ADDED",
            entity_type="VERIFICATION_EVIDENCE",
            entity_id=evidence.pk,
            metadata={
                "verification_id": str(verification.pk),
                "evidence_type": evidence.evidence_type,
            },
            ip_address=ip_address,
        )
    return evidence
