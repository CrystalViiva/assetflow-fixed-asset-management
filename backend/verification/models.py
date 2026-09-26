"""Physical observations, campaign scope, reconciliation exceptions, and evidence metadata."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CampaignStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class CampaignScope(models.TextChoices):
    ORGANIZATION = "ORGANIZATION", "Organization"
    DEPARTMENT = "DEPARTMENT", "Department"
    LOCATION = "LOCATION", "Location"


class VerificationResult(models.TextChoices):
    VERIFIED = "VERIFIED", "Verified"
    LOCATION_MISMATCH = "LOCATION_MISMATCH", "Location mismatch"
    CUSTODY_MISMATCH = "CUSTODY_MISMATCH", "Custody mismatch"
    CONDITION_MISMATCH = "CONDITION_MISMATCH", "Condition mismatch"
    ASSET_NOT_FOUND = "ASSET_NOT_FOUND", "Asset not found"
    TAG_MISSING = "TAG_MISSING", "Tag missing"
    DAMAGED = "DAMAGED", "Damaged"
    UNREGISTERED_ASSET = "UNREGISTERED_ASSET", "Unregistered asset"
    DUPLICATE_TAG = "DUPLICATE_TAG", "Duplicate tag"
    OTHER_EXCEPTION = "OTHER_EXCEPTION", "Other exception"


class PhysicalCondition(models.TextChoices):
    GOOD = "GOOD", "Good"
    FAIR = "FAIR", "Fair"
    DAMAGED = "DAMAGED", "Damaged"
    CRITICAL = "CRITICAL", "Critical"
    UNKNOWN = "UNKNOWN", "Unknown"


class ExceptionType(models.TextChoices):
    LOCATION_MISMATCH = "LOCATION_MISMATCH", "Location mismatch"
    DEPARTMENT_MISMATCH = "DEPARTMENT_MISMATCH", "Department mismatch"
    CUSTODY_MISMATCH = "CUSTODY_MISMATCH", "Custody mismatch"
    CONDITION_MISMATCH = "CONDITION_MISMATCH", "Condition mismatch"
    TAG_MISSING = "TAG_MISSING", "Tag missing"
    TAG_MISMATCH = "TAG_MISMATCH", "Tag mismatch"
    ASSET_NOT_FOUND = "ASSET_NOT_FOUND", "Asset not found"
    DAMAGED_ASSET = "DAMAGED_ASSET", "Damaged asset"
    UNREGISTERED_ASSET = "UNREGISTERED_ASSET", "Unregistered asset"
    DUPLICATE_TAG = "DUPLICATE_TAG", "Duplicate tag"
    LIFECYCLE_MISMATCH = "LIFECYCLE_MISMATCH", "Lifecycle mismatch"
    OTHER = "OTHER", "Other"


class ExceptionSeverity(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class ExceptionStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    UNDER_REVIEW = "UNDER_REVIEW", "Under review"
    RESOLVED = "RESOLVED", "Resolved"
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"


class EvidenceType(models.TextChoices):
    PHOTO = "PHOTO", "Photo"
    DOCUMENT = "DOCUMENT", "Document"
    SCAN = "SCAN", "Scan"
    NOTE = "NOTE", "Note"
    OTHER = "OTHER", "Other"


class VerificationCampaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="verification_campaigns",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT
    )
    scope_type = models.CharField(max_length=16, choices=CampaignScope.choices)
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verification_campaigns",
    )
    location = models.ForeignKey(
        "organizations.Location",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verification_campaigns",
    )
    start_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verification_campaigns_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verification_campaigns_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-start_date", "name")
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=CampaignStatus.values), name="verify_campaign_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(scope_type__in=CampaignScope.values), name="verify_campaign_scope_valid"
            ),
            models.CheckConstraint(
                condition=Q(due_date__isnull=True) | Q(due_date__gte=models.F("start_date")),
                name="verify_campaign_due_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        scope_type=CampaignScope.ORGANIZATION,
                        department__isnull=True,
                        location__isnull=True,
                    )
                    | Q(
                        scope_type=CampaignScope.DEPARTMENT,
                        department__isnull=False,
                        location__isnull=True,
                    )
                    | Q(
                        scope_type=CampaignScope.LOCATION,
                        department__isnull=True,
                        location__isnull=False,
                    )
                ),
                name="verify_campaign_scope_fields_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=CampaignStatus.DRAFT,
                        opened_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status__in=(CampaignStatus.OPEN, CampaignStatus.IN_PROGRESS),
                        opened_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=CampaignStatus.COMPLETED,
                        opened_at__isnull=False,
                        completed_at__isnull=False,
                    )
                    | Q(status=CampaignStatus.CANCELLED, completed_at__isnull=True)
                ),
                name="verify_campaign_timestamps_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "status", "start_date"),
                name="verify_campaign_org_status_idx",
            ),
            models.Index(
                fields=("organization", "department", "status"), name="verify_campaign_org_dept_idx"
            ),
            models.Index(
                fields=("organization", "location", "status"), name="verify_campaign_org_loc_idx"
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.scope_type == CampaignScope.ORGANIZATION and (
            self.department_id or self.location_id
        ):
            errors["scope_type"] = "Organization scope cannot specify a department or location."
        elif self.scope_type == CampaignScope.DEPARTMENT:
            if not self.department_id or self.location_id:
                errors["department"] = "Department scope requires only a department."
            elif self.department.organization_id != self.organization_id:
                errors["department"] = "Department must belong to the campaign organization."
        elif self.scope_type == CampaignScope.LOCATION:
            if not self.location_id or self.department_id:
                errors["location"] = "Location scope requires only a location."
            elif self.location.organization_id != self.organization_id:
                errors["location"] = "Location must belong to the campaign organization."
        if self.due_date and self.start_date and self.due_date < self.start_date:
            errors["due_date"] = "Due date cannot precede the campaign start date."
        for field in ("created_by", "updated_by"):
            user = getattr(self, field, None)
            if user and user.organization_id != self.organization_id:
                errors[field] = "User must belong to the campaign organization."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        raise ValidationError("Verification campaigns are retained as audit history.")


class PhysicalVerification(models.Model):
    """Immutable physical facts plus a service-maintained reconciliation summary."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="physical_verifications",
    )
    campaign = models.ForeignKey(
        VerificationCampaign, on_delete=models.PROTECT, related_name="verifications"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="physical_verifications",
    )
    verified_at = models.DateTimeField(default=timezone.now)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="physical_verifications"
    )
    result = models.CharField(max_length=24, choices=VerificationResult.choices)
    observed_location = models.ForeignKey(
        "organizations.Location",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_observations",
    )
    observed_department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_observations",
    )
    observed_custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custody_observations",
    )
    observed_condition = models.CharField(
        max_length=12, choices=PhysicalCondition.choices, default=PhysicalCondition.UNKNOWN
    )
    observed_asset_tag = models.CharField(max_length=64, blank=True)
    observed_description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-verified_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("campaign", "asset"),
                condition=Q(asset__isnull=False),
                name="uniq_campaign_asset_verification",
            ),
            models.CheckConstraint(
                condition=Q(result__in=VerificationResult.values),
                name="physical_verify_result_valid",
            ),
            models.CheckConstraint(
                condition=Q(observed_condition__in=PhysicalCondition.values),
                name="physical_condition_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(result=VerificationResult.UNREGISTERED_ASSET, asset__isnull=True)
                    | Q(
                        result__in=[
                            r
                            for r in VerificationResult.values
                            if r != VerificationResult.UNREGISTERED_ASSET
                        ],
                        asset__isnull=False,
                    )
                ),
                name="physical_verify_asset_result_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "campaign", "result"), name="physical_verify_org_camp_idx"
            ),
            models.Index(fields=("organization", "asset"), name="physical_verify_org_asset_idx"),
            models.Index(
                fields=("organization", "verified_at"), name="physical_verify_org_time_idx"
            ),
            models.Index(
                fields=("organization", "observed_asset_tag"), name="physical_verify_org_tag_idx"
            ),
            models.Index(
                fields=("organization", "observed_department"),
                name="physical_verify_org_dept_idx",
            ),
            models.Index(
                fields=("organization", "observed_location"), name="physical_verify_org_loc_idx"
            ),
            models.Index(
                fields=("organization", "observed_custodian"),
                name="physical_verify_org_user_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.campaign_id
            and self.organization_id
            and self.campaign.organization_id != self.organization_id
        ):
            errors["campaign"] = "Campaign must belong to the verification organization."
        if (
            self.asset_id
            and self.organization_id
            and self.asset.organization_id != self.organization_id
        ):
            errors["asset"] = "Asset must belong to the verification organization."
        for field in (
            "verified_by",
            "observed_custodian",
            "observed_department",
            "observed_location",
        ):
            related = getattr(self, field, None)
            if related and related.organization_id != self.organization_id:
                errors[field] = "Observed reference must belong to the verification organization."
        if (self.result == VerificationResult.UNREGISTERED_ASSET) != (self.asset_id is None):
            errors["asset"] = (
                "Unregistered observations have no asset link; registered results require one."
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous:
                changed = [
                    field.name
                    for field in self._meta.concrete_fields
                    if field.name not in {"id", "updated_at"}
                    and getattr(previous, field.attname) != getattr(self, field.attname)
                ]
                if changed:
                    raise ValidationError("Physical observation facts are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Physical verification history cannot be deleted.")

    def __str__(self):
        tag = self.observed_asset_tag or (self.asset.asset_tag if self.asset_id else "Unregistered")
        return f"{tag} @ {self.verified_at:%Y-%m-%d}"


class VerificationException(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="verification_exceptions",
    )
    campaign = models.ForeignKey(
        VerificationCampaign, on_delete=models.PROTECT, related_name="exceptions"
    )
    verification = models.ForeignKey(
        PhysicalVerification, on_delete=models.PROTECT, related_name="exceptions"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verification_exceptions",
    )
    exception_type = models.CharField(max_length=24, choices=ExceptionType.choices)
    severity = models.CharField(
        max_length=8, choices=ExceptionSeverity.choices, default=ExceptionSeverity.MEDIUM
    )
    status = models.CharField(
        max_length=16, choices=ExceptionStatus.choices, default=ExceptionStatus.OPEN
    )
    description = models.TextField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verification_exceptions_assigned",
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    resolution_reference = models.CharField(max_length=200, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verification_exceptions_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("verification", "exception_type"), name="uniq_verify_exception_type"
            ),
            models.CheckConstraint(
                condition=Q(exception_type__in=ExceptionType.values),
                name="verify_exception_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(severity__in=ExceptionSeverity.values),
                name="verify_exception_severity_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=ExceptionStatus.values), name="verify_exception_status_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=(ExceptionStatus.OPEN, ExceptionStatus.UNDER_REVIEW),
                        resolved_at__isnull=True,
                        resolved_by__isnull=True,
                    )
                    | Q(
                        status__in=(
                            ExceptionStatus.RESOLVED,
                            ExceptionStatus.ACCEPTED,
                            ExceptionStatus.REJECTED,
                        ),
                        resolved_at__isnull=False,
                        resolved_by__isnull=False,
                    )
                ),
                name="verify_exception_resolution_valid",
            ),
            models.CheckConstraint(
                condition=Q(assigned_at__isnull=True) | Q(assigned_to__isnull=False),
                name="verify_exception_assign_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "campaign", "status"), name="verify_exc_org_camp_idx"
            ),
            models.Index(
                fields=("organization", "asset", "status"), name="verify_exc_org_asset_idx"
            ),
            models.Index(
                fields=("organization", "status", "severity"), name="verify_exc_org_state_idx"
            ),
            models.Index(
                fields=("organization", "assigned_to", "status"), name="verify_exc_org_user_idx"
            ),
            models.Index(
                fields=("organization", "exception_type", "created_at"),
                name="verify_exc_org_type_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.campaign_id
            and self.organization_id
            and self.campaign.organization_id != self.organization_id
        ):
            errors["campaign"] = "Campaign must belong to the exception organization."
        if self.verification_id:
            if self.verification.organization_id != self.organization_id:
                errors["verification"] = "Verification must belong to the exception organization."
            if self.verification.campaign_id != self.campaign_id:
                errors["verification"] = "Verification must belong to the exception campaign."
            if self.verification.asset_id != self.asset_id:
                errors["asset"] = "Exception asset must match its verification."
        if self.asset_id and self.asset.organization_id != self.organization_id:
            errors["asset"] = "Asset must belong to the exception organization."
        for field in ("assigned_to", "resolved_by"):
            user = getattr(self, field, None)
            if user and user.organization_id != self.organization_id:
                errors[field] = "User must belong to the exception organization."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.exception_type} ({self.status})"

    def delete(self, *args, **kwargs):
        raise ValidationError("Verification exceptions cannot be deleted.")


class VerificationEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="verification_evidence"
    )
    verification = models.ForeignKey(
        PhysicalVerification, on_delete=models.PROTECT, related_name="evidence"
    )
    exception = models.ForeignKey(
        VerificationException,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="evidence",
    )
    evidence_type = models.CharField(max_length=12, choices=EvidenceType.choices)
    file_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=128, blank=True)
    storage_key = models.CharField(max_length=512, blank=True)
    external_reference = models.CharField(max_length=512, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="verification_evidence"
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-captured_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(evidence_type__in=EvidenceType.values),
                name="verify_evidence_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(evidence_type=EvidenceType.NOTE)
                | ~Q(storage_key="", external_reference=""),
                name="verify_evidence_reference_present",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "verification", "captured_at"),
                name="verify_evid_org_record_idx",
            ),
            models.Index(fields=("organization", "exception"), name="verify_evid_org_exc_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.verification_id and self.verification.organization_id != self.organization_id:
            errors["verification"] = "Verification must belong to the evidence organization."
        if self.exception_id:
            if self.exception.organization_id != self.organization_id:
                errors["exception"] = "Exception must belong to the evidence organization."
            if self.exception.verification_id != self.verification_id:
                errors["exception"] = "Exception must refer to the selected verification."
        if self.captured_by_id and self.captured_by.organization_id != self.organization_id:
            errors["captured_by"] = "User must belong to the evidence organization."
        if self.evidence_type != EvidenceType.NOTE and not (
            self.storage_key or self.external_reference
        ):
            errors["storage_key"] = (
                "Evidence metadata requires a storage key or external reference."
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.evidence_type}: {self.file_name or self.description[:40]}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Verification evidence metadata cannot be deleted.")
