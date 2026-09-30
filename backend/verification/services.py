"""Transactional campaign, observation, reconciliation, and exception operations."""

import hashlib
import re
import struct
import tempfile
import zlib
from pathlib import PurePosixPath
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import storages
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import UserRole
from assets.models import Asset, AssetStatus
from audit.services import record_event
from transfers.models import AssetAssignment
from verification.models import (
    CampaignScope,
    CampaignStatus,
    EvidenceIntegrityStatus,
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
    _update_verification_result(verification, result=result, actor=actor, ip_address=ip_address)
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
    uploaded_file=None,
    ip_address=None,
):
    organization = _organization(actor)
    spool = None
    digest = ""
    byte_size = None
    detected_type = content_type
    binary_key = ""
    stored_key = ""
    if uploaded_file is not None:
        if storage_key:
            raise ValidationError({"storage_key": "Uploaded evidence uses a server storage key."})
        spool, byte_size, digest, detected_type = _spool_evidence_upload(uploaded_file)
        file_name = _safe_evidence_filename(uploaded_file.name)

    try:
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
            if uploaded_file is not None:
                binary_key = (
                    f"evidence/{organization.pk}/{uuid4().hex}/{uuid4().hex}."
                    f"{_EVIDENCE_EXTENSIONS[detected_type]}"
                )
            evidence = VerificationEvidence(
                organization=organization,
                verification=verification,
                exception=exception,
                evidence_type=evidence_type,
                file_name=file_name,
                content_type=detected_type,
                storage_key=storage_key,
                external_reference=external_reference,
                captured_at=captured_at or timezone.now(),
                captured_by=actor,
                description=description,
                binary_storage_key=binary_key,
                byte_size=None,
                sha256="",
                integrity_status=(
                    EvidenceIntegrityStatus.PENDING
                    if uploaded_file is not None
                    else EvidenceIntegrityStatus.METADATA_ONLY
                    if evidence_type == "NOTE"
                    else EvidenceIntegrityStatus.LEGACY_UNVERIFIED
                ),
            )
            evidence.full_clean()
            evidence.save()
            _audit(
                organization=organization,
                actor=actor,
                action=(
                    "VERIFICATION_EVIDENCE_UPLOAD_STARTED"
                    if uploaded_file is not None
                    else "VERIFICATION_EVIDENCE_ADDED"
                ),
                entity_type="VERIFICATION_EVIDENCE",
                entity_id=evidence.pk,
                metadata={
                    "verification_id": str(verification.pk),
                    "evidence_type": evidence.evidence_type,
                    "integrity_status": evidence.integrity_status,
                },
                ip_address=ip_address,
            )

        if uploaded_file is not None:
            storage = storages["assetflow_private"]
            try:
                spool.seek(0)
                stored_key = storage.save(binary_key, File(spool, name=file_name))
                _verify_storage_object(storage, stored_key, byte_size, digest)
                with transaction.atomic():
                    evidence = VerificationEvidence.objects.select_for_update().get(pk=evidence.pk)
                    evidence.binary_storage_key = stored_key
                    evidence.byte_size = byte_size
                    evidence.sha256 = digest
                    evidence.uploaded_at = timezone.now()
                    evidence.integrity_verified_at = timezone.now()
                    evidence.integrity_status = EvidenceIntegrityStatus.VERIFIED
                    evidence.save(
                        update_fields=(
                            "binary_storage_key",
                            "byte_size",
                            "sha256",
                            "uploaded_at",
                            "integrity_verified_at",
                            "integrity_status",
                        )
                    )
                    _audit(
                        organization=organization,
                        actor=actor,
                        action="VERIFICATION_EVIDENCE_VERIFIED",
                        entity_type="VERIFICATION_EVIDENCE",
                        entity_id=evidence.pk,
                        metadata={
                            "verification_id": str(verification.pk),
                            "byte_size": byte_size,
                            "sha256": digest,
                        },
                        ip_address=ip_address,
                    )
            except Exception as exc:
                deleted = _delete_private_object(stored_key or binary_key)
                _fail_pending_evidence(evidence.pk, actor, ip_address, clear_key=deleted)
                raise EvidenceStorageError("Evidence upload could not be verified.") from exc
        return evidence
    finally:
        if spool is not None:
            spool.close()


_EVIDENCE_SIGNATURES = {
    "application/pdf": (b"%PDF-", 5),
    "image/jpeg": (b"\xff\xd8\xff", 3),
    "image/png": (b"\x89PNG\r\n\x1a\n", 8),
}
_EVIDENCE_EXTENSIONS = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}


class EvidenceStorageError(Exception):
    """Private evidence storage or read-back verification failed."""


def _safe_evidence_filename(value):
    name = PurePosixPath(str(value).replace("\\", "/")).name
    name = "".join(char for char in name if ord(char) >= 32 and ord(char) != 127)
    name = re.sub(r"[/\\]+", "_", name).strip(" .")[:255]
    return name or "evidence"


def _spool_evidence_upload(upload):
    maximum = settings.EVIDENCE_MAX_UPLOAD_BYTES
    if maximum < 1:
        raise ValidationError("Evidence upload limit is not configured correctly.")
    spool = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
    digest = hashlib.sha256()
    size = 0
    header = bytearray()
    try:
        for chunk in upload.chunks():
            size += len(chunk)
            if size > maximum:
                raise ValidationError({"file": "Evidence exceeds the configured size limit."})
            if len(header) < 8:
                header.extend(chunk[: 8 - len(header)])
            digest.update(chunk)
            spool.write(chunk)
        if size == 0:
            raise ValidationError({"file": "Evidence files cannot be empty."})
        detected = next(
            (
                mime
                for mime, (signature, count) in _EVIDENCE_SIGNATURES.items()
                if bytes(header[:count]) == signature
            ),
            None,
        )
        if detected is None:
            raise ValidationError({"file": "Only PDF, JPEG, and PNG evidence is supported."})
        spool.seek(0)
        try:
            _validate_evidence_structure(spool, detected, size)
        except ValueError as exc:
            raise ValidationError({"file": "Evidence file structure is invalid."}) from exc
        spool.seek(0)
        return spool, size, digest.hexdigest(), detected
    except Exception:
        spool.close()
        raise


def _validate_evidence_structure(spool, content_type, size):
    if content_type == "image/png":
        _validate_png(spool, size)
    elif content_type == "image/jpeg":
        _validate_jpeg(spool)
    elif content_type == "application/pdf":
        _validate_pdf(spool, size)
    else:
        raise ValueError("unsupported evidence type")


def _read_exact(stream, size):
    value = stream.read(size)
    if len(value) != size:
        raise ValueError("truncated evidence structure")
    return value


def _validate_png(spool, size):
    if _read_exact(spool, 8) != b"\x89PNG\r\n\x1a\n":
        raise ValueError("invalid PNG signature")
    first = True
    seen_idat = False
    idat_ended = False
    seen_palette = False
    color_type = None
    while spool.tell() < size:
        length, chunk_type = struct.unpack(">I4s", _read_exact(spool, 8))
        if length > size or spool.tell() + length + 4 > size:
            raise ValueError("invalid PNG chunk length")
        if not re.fullmatch(rb"[A-Za-z]{4}", chunk_type):
            raise ValueError("invalid PNG chunk name")
        if first:
            if chunk_type != b"IHDR" or length != 13:
                raise ValueError("PNG IHDR must be first")
            first = False
        elif chunk_type == b"IHDR":
            raise ValueError("duplicate PNG IHDR")

        crc = zlib.crc32(chunk_type)
        data_left = length
        ihdr = bytearray()
        while data_left:
            part = _read_exact(spool, min(data_left, 64 * 1024))
            crc = zlib.crc32(part, crc)
            if chunk_type == b"IHDR":
                ihdr.extend(part)
            data_left -= len(part)
        expected_crc = struct.unpack(">I", _read_exact(spool, 4))[0]
        if crc & 0xFFFFFFFF != expected_crc:
            raise ValueError("invalid PNG chunk checksum")

        if chunk_type == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", ihdr
            )
            depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
            if (
                width < 1
                or height < 1
                or color not in depths
                or depth not in depths[color]
                or compression != 0
                or filtering != 0
                or interlace not in (0, 1)
            ):
                raise ValueError("invalid PNG IHDR values")
            color_type = color
        elif chunk_type == b"PLTE":
            if (
                seen_palette
                or seen_idat
                or color_type in (0, 4)
                or length == 0
                or length > 768
                or length % 3
            ):
                raise ValueError("invalid PNG palette")
            seen_palette = True
        elif chunk_type == b"IDAT":
            if idat_ended or length == 0 or (color_type == 3 and not seen_palette):
                raise ValueError("invalid PNG image data ordering")
            seen_idat = True
        elif seen_idat and chunk_type != b"IEND":
            idat_ended = True

        critical = chunk_type[0] & 0x20 == 0
        if critical and chunk_type not in (b"IHDR", b"PLTE", b"IDAT", b"IEND"):
            raise ValueError("unknown critical PNG chunk")
        if chunk_type == b"IEND":
            if length != 0 or not seen_idat or spool.tell() != size:
                raise ValueError("invalid PNG IEND")
            return
    raise ValueError("PNG is missing IEND")


class _BufferedByteReader:
    def __init__(self, stream):
        self.stream = stream
        self.buffer = b""
        self.offset = 0

    def byte(self):
        if self.offset >= len(self.buffer):
            self.buffer = self.stream.read(64 * 1024)
            self.offset = 0
            if not self.buffer:
                raise ValueError("truncated JPEG structure")
        value = self.buffer[self.offset]
        self.offset += 1
        return value

    def skip(self, length):
        while length:
            if self.offset >= len(self.buffer):
                self.buffer = self.stream.read(min(64 * 1024, length))
                self.offset = 0
                if not self.buffer:
                    raise ValueError("truncated JPEG segment")
            amount = min(length, len(self.buffer) - self.offset)
            self.offset += amount
            length -= amount

    def has_more(self):
        if self.offset < len(self.buffer):
            return True
        self.buffer = self.stream.read(1)
        self.offset = 0
        return bool(self.buffer)


def _jpeg_entropy_marker(reader):
    while True:
        value = reader.byte()
        if value != 0xFF:
            continue
        marker = reader.byte()
        while marker == 0xFF:
            marker = reader.byte()
        if marker == 0 or 0xD0 <= marker <= 0xD7:
            continue
        return marker


def _validate_jpeg(spool):
    spool.seek(0)
    reader = _BufferedByteReader(spool)
    if reader.byte() != 0xFF or reader.byte() != 0xD8:
        raise ValueError("invalid JPEG SOI")
    has_frame = False
    has_scan = False
    marker = None
    frame_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while True:
        if marker is None:
            if reader.byte() != 0xFF:
                raise ValueError("invalid JPEG marker framing")
            marker = reader.byte()
            while marker == 0xFF:
                marker = reader.byte()
        current = marker
        marker = None
        if current == 0xD9:
            if not has_frame or not has_scan or reader.has_more():
                raise ValueError("invalid JPEG end marker")
            return
        if current == 0x01:  # TEM is a standalone marker.
            continue
        if current in (0x00, 0xD8) or 0xD0 <= current <= 0xD7:
            raise ValueError("unexpected standalone JPEG marker")
        segment_length = (reader.byte() << 8) | reader.byte()
        if segment_length < 2:
            raise ValueError("invalid JPEG segment length")
        payload_length = segment_length - 2
        if current in frame_markers:
            if payload_length < 6:
                raise ValueError("truncated JPEG frame header")
            precision = reader.byte()
            height = (reader.byte() << 8) | reader.byte()
            width = (reader.byte() << 8) | reader.byte()
            components = reader.byte()
            reader.skip(payload_length - 6)
            if precision == 0 or width == 0 or height == 0 or components == 0:
                raise ValueError("invalid JPEG frame dimensions")
            if segment_length != 8 + 3 * components:
                raise ValueError("invalid JPEG frame component table")
            has_frame = True
        elif current == 0xDA:
            if payload_length < 4:
                raise ValueError("truncated JPEG scan header")
            components = reader.byte()
            reader.skip(payload_length - 1)
            if components == 0 or segment_length != 6 + 2 * components:
                raise ValueError("invalid JPEG scan component table")
            has_scan = True
            marker = _jpeg_entropy_marker(reader)
        else:
            reader.skip(payload_length)


_PDF_XREF_WINDOW_BYTES = 64 * 1024
_PDF_MAX_OBJECT_NUMBER = 9_999_999_999


def _pdf_line(data, position):
    """Read one CR, LF, or CRLF terminated line from a bounded PDF buffer."""
    end = position
    while end < len(data) and data[end] not in (0x0A, 0x0D):
        end += 1
    if end == len(data):
        raise ValueError("PDF line exceeds the validation window or is truncated")
    next_position = end + 1
    if data[end] == 0x0D and next_position < len(data) and data[next_position] == 0x0A:
        next_position += 1
    return data[position:end], next_position


def _pdf_dictionary_end(data, position, end):
    """Find a balanced dictionary and its top-level indirect /Root reference."""
    while position < end and data[position] in b"\x00\t\n\x0c\r ":
        position += 1
    if data[position : position + 2] != b"<<":
        raise ValueError("PDF trailer dictionary is missing")

    depth = 1
    position += 2
    has_root = False
    while position < end:
        value = data[position]
        if value == ord("%"):
            while position < end and data[position] not in (0x0A, 0x0D):
                position += 1
        elif value == ord("("):
            string_depth = 1
            position += 1
            while position < end and string_depth:
                current = data[position]
                if current == ord("\\"):
                    position += 2
                    continue
                if current == ord("("):
                    string_depth += 1
                elif current == ord(")"):
                    string_depth -= 1
                position += 1
            if string_depth:
                raise ValueError("truncated PDF trailer string")
            continue
        elif value == ord("<"):
            if data[position : position + 2] == b"<<":
                depth += 1
                position += 2
                continue
            position += 1
            while position < end and data[position] != ord(">"):
                position += 1
            if position == end:
                raise ValueError("truncated PDF trailer hex string")
            position += 1
            continue
        elif value == ord(">") and data[position : position + 2] == b">>":
            depth -= 1
            position += 2
            if depth == 0:
                if not has_root:
                    raise ValueError("PDF trailer has no indirect /Root reference")
                return position
            continue
        elif depth == 1 and data.startswith(b"/Root", position):
            after_name = position + 5
            if after_name == end or data[after_name] in b"\x00\t\n\x0c\r ()<>/[]%":
                reference = re.match(rb"/Root\s+[0-9]{1,10}\s+[0-9]{1,5}\s+R\b", data[position:end])
                if reference:
                    has_root = True
        position += 1
    raise ValueError("unterminated PDF trailer dictionary")


def _validate_classic_pdf_xref(data, startxref_position, file_size):
    """Validate a bounded classic xref table and its trailer dictionary."""
    if startxref_position <= 0 or startxref_position >= len(data):
        raise ValueError("PDF xref table exceeds the validation window")
    table = data[:startxref_position]
    if not table.startswith(b"xref") or len(table) < 5 or table[4] not in b"\x00\t\n\x0c\r ":
        raise ValueError("PDF startxref does not point to a classic xref token")

    position = 4
    line, position = _pdf_line(table, position)
    if line.strip(b"\x00\t\x0c "):
        raise ValueError("classic PDF xref token must end its line")

    subsection_count = 0
    trailer_position = None
    while position < len(table):
        line, position = _pdf_line(table, position)
        stripped = line.strip(b"\x00\t\x0c ")
        if stripped == b"trailer":
            trailer_position = position
            break
        header = re.fullmatch(rb"([0-9]{1,10})[\x00\t\x0c ]+([0-9]{1,10})[\x00\t\x0c ]*", line)
        if header is None:
            raise ValueError("invalid classic PDF xref subsection header")
        first_object = int(header.group(1))
        entry_count = int(header.group(2))
        if (
            entry_count < 1
            or first_object + entry_count - 1 > _PDF_MAX_OBJECT_NUMBER
            or entry_count > (len(table) - position) // 19
        ):
            raise ValueError("classic PDF xref subsection count is outside the validation bound")

        for _ in range(entry_count):
            entry, position = _pdf_line(table, position)
            entry_match = re.fullmatch(
                rb"[0-9]{10}[\x00\t\x0c ]+([0-9]{5})[\x00\t\x0c ]+([nf])[\x00\t\x0c ]*",
                entry,
            )
            if entry_match is None:
                raise ValueError("invalid or truncated classic PDF xref entry")
            offset = int(entry[:10])
            generation = int(entry_match.group(1))
            if generation > 65_535 or (entry_match.group(2) == b"n" and offset >= file_size):
                raise ValueError("classic PDF xref entry contains an invalid reference")
        subsection_count += 1

    if subsection_count == 0 or trailer_position is None:
        raise ValueError("classic PDF xref table requires a subsection and trailer")
    dictionary_end = _pdf_dictionary_end(table, trailer_position, len(table))
    if table[dictionary_end:].strip(b"\x00\t\n\x0c\r "):
        raise ValueError("unexpected content between PDF trailer and startxref")


def _validate_pdf(spool, size):
    spool.seek(0)
    header = spool.read(16)
    if not re.match(rb"%PDF-(?:1\.[0-7]|2\.0)(?:\r\n|\r|\n)", header):
        raise ValueError("invalid PDF header")
    if size < 32:
        raise ValueError("truncated PDF")
    tail_size = min(size, 64 * 1024)
    spool.seek(size - tail_size)
    tail = spool.read(tail_size)
    match = re.search(rb"startxref\s+([0-9]{1,20})\s+%%EOF\s*\Z", tail)
    if match is None:
        raise ValueError("PDF is missing a valid trailer")
    offset = int(match.group(1))
    if offset >= size:
        raise ValueError("PDF cross-reference offset is outside the file")
    spool.seek(offset)
    xref_window = spool.read(min(_PDF_XREF_WINDOW_BYTES, size - offset))
    startxref_position = size - tail_size + match.start() - offset
    if startxref_position < 0 or startxref_position >= len(xref_window):
        raise ValueError("PDF xref table and trailer exceed the validation window")
    # M10.6 structurally validates classic xref tables. Xref-stream PDFs are
    # intentionally rejected until a bounded validator for that format exists.
    _validate_classic_pdf_xref(xref_window, startxref_position, size)


def _verify_storage_object(storage, key, expected_size, expected_digest):
    digest = hashlib.sha256()
    size = 0
    with storage.open(key, "rb") as stored:
        for chunk in iter(lambda: stored.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    if size != expected_size or digest.hexdigest() != expected_digest:
        raise EvidenceStorageError("Stored evidence failed its integrity check.")


def _delete_private_object(key):
    if not key:
        return True
    try:
        storages["assetflow_private"].delete(key)
        return True
    except Exception:
        # A retryable cleanup task handles failed/dead-worker uploads by their DB key.
        return False


def _fail_pending_evidence(evidence_id, actor, ip_address, *, clear_key):
    with transaction.atomic():
        evidence = VerificationEvidence.objects.select_for_update().get(pk=evidence_id)
        if evidence.integrity_status != EvidenceIntegrityStatus.PENDING:
            return evidence
        if clear_key:
            evidence.binary_storage_key = ""
            evidence.integrity_status = EvidenceIntegrityStatus.FAILED
            evidence.content_type = ""
            evidence.save(update_fields=("binary_storage_key", "integrity_status", "content_type"))
        _audit(
            organization=evidence.organization,
            actor=actor,
            action=(
                "VERIFICATION_EVIDENCE_UPLOAD_FAILED"
                if clear_key
                else "VERIFICATION_EVIDENCE_UPLOAD_CLEANUP_PENDING"
            ),
            entity_type="VERIFICATION_EVIDENCE",
            entity_id=evidence.pk,
            metadata={"evidence_type": evidence.evidence_type},
            ip_address=ip_address,
        )


def open_verified_evidence(*, evidence, actor, ip_address=None):
    if evidence.organization_id != getattr(actor, "organization_id", None):
        raise ValidationError("Evidence was not found in your organization.")
    if evidence.integrity_status != EvidenceIntegrityStatus.VERIFIED:
        raise EvidenceIntegrityError("Evidence is not available for retrieval.")
    storage = storages["assetflow_private"]
    spool = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
    try:
        digest = hashlib.sha256()
        size = 0
        with storage.open(evidence.binary_storage_key, "rb") as stored:
            for chunk in iter(lambda: stored.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
                spool.write(chunk)
        if size != evidence.byte_size or digest.hexdigest() != evidence.sha256:
            raise EvidenceIntegrityError("Stored evidence digest mismatch.")
        spool.seek(0)
    except Exception as exc:
        spool.close()
        with transaction.atomic():
            current = VerificationEvidence.objects.select_for_update().get(pk=evidence.pk)
            if current.integrity_status == EvidenceIntegrityStatus.VERIFIED:
                current.integrity_status = EvidenceIntegrityStatus.CORRUPT
                current.save(update_fields=("integrity_status",))
                _audit(
                    organization=current.organization,
                    actor=actor,
                    action="VERIFICATION_EVIDENCE_INTEGRITY_FAILED",
                    entity_type="VERIFICATION_EVIDENCE",
                    entity_id=current.pk,
                    metadata={"reason": "stored_bytes_mismatch_or_missing"},
                    ip_address=ip_address,
                )
        raise EvidenceIntegrityError("Evidence failed its integrity check.") from exc
    try:
        _audit(
            organization=evidence.organization,
            actor=actor,
            action="VERIFICATION_EVIDENCE_DOWNLOADED",
            entity_type="VERIFICATION_EVIDENCE",
            entity_id=evidence.pk,
            metadata={"sha256": evidence.sha256},
            ip_address=ip_address,
        )
    except Exception:
        spool.close()
        raise
    return spool


class EvidenceIntegrityError(Exception):
    """Evidence is unavailable or its stored bytes do not match the recorded digest."""


def cleanup_stale_evidence_uploads(*, older_than, limit=100):
    """Mark abandoned synchronous uploads failed and retry private-object cleanup."""
    cutoff = timezone.now() - older_than
    ids = list(
        VerificationEvidence.objects.filter(
            integrity_status=EvidenceIntegrityStatus.PENDING, created_at__lt=cutoff
        )
        .order_by("created_at", "pk")
        .values_list("pk", flat=True)[:limit]
    )
    cleaned = 0
    for evidence_id in ids:
        with transaction.atomic():
            evidence = VerificationEvidence.objects.select_for_update().get(pk=evidence_id)
            if evidence.integrity_status != EvidenceIntegrityStatus.PENDING:
                continue
            key = evidence.binary_storage_key
            try:
                if key:
                    storages["assetflow_private"].delete(key)
            except Exception:
                continue
            evidence.binary_storage_key = ""
            evidence.integrity_status = EvidenceIntegrityStatus.FAILED
            evidence.content_type = ""
            evidence.save(update_fields=("binary_storage_key", "integrity_status", "content_type"))
            _audit(
                organization=evidence.organization,
                actor=None,
                action="VERIFICATION_EVIDENCE_ABANDONED_UPLOAD_CLEANED",
                entity_type="VERIFICATION_EVIDENCE",
                entity_id=evidence.pk,
                metadata={},
            )
            cleaned += 1
    return cleaned
