"""Durable assurance executions, findings, and per-run detection history."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class AssuranceRunType(models.TextChoices):
    FULL = "FULL", "Full"
    PHYSICAL = "PHYSICAL", "Physical"
    FINANCIAL = "FINANCIAL", "Financial"
    OPERATIONAL = "OPERATIONAL", "Operational"


class AssuranceRunStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class FindingType(models.TextChoices):
    LOCATION_MISMATCH = "LOCATION_MISMATCH", "Location mismatch"
    DEPARTMENT_MISMATCH = "DEPARTMENT_MISMATCH", "Department mismatch"
    CUSTODY_MISMATCH = "CUSTODY_MISMATCH", "Custody mismatch"
    MISSING_PHYSICAL_VERIFICATION = "MISSING_PHYSICAL_VERIFICATION", "Missing physical verification"
    ASSET_NOT_FOUND = "ASSET_NOT_FOUND", "Asset not found"
    UNREGISTERED_ASSET = "UNREGISTERED_ASSET", "Unregistered asset"
    TAG_MISMATCH = "TAG_MISMATCH", "Tag mismatch"
    DUPLICATE_TAG = "DUPLICATE_TAG", "Duplicate tag"
    CONDITION_EXCEPTION = "CONDITION_EXCEPTION", "Condition exception"
    LIFECYCLE_MISMATCH = "LIFECYCLE_MISMATCH", "Lifecycle mismatch"
    DISPOSAL_STATUS_MISMATCH = "DISPOSAL_STATUS_MISMATCH", "Disposal status mismatch"
    DEPRECIATION_EXCEPTION = "DEPRECIATION_EXCEPTION", "Depreciation exception"
    BOOK_VALUE_EXCEPTION = "BOOK_VALUE_EXCEPTION", "Book value exception"
    STALE_RECORD = "STALE_RECORD", "Stale record"
    OPEN_WORKFLOW = "OPEN_WORKFLOW", "Open workflow"
    MISSING_EVIDENCE = "MISSING_EVIDENCE", "Missing evidence"


class FindingSeverity(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class FindingStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    UNDER_REVIEW = "UNDER_REVIEW", "Under review"
    RESOLVED = "RESOLVED", "Resolved"
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"


class FindingSource(models.TextChoices):
    ASSET_MASTER = "ASSET_MASTER", "Asset master"
    PHYSICAL_VERIFICATION = "PHYSICAL_VERIFICATION", "Physical verification"
    DEPRECIATION = "DEPRECIATION", "Depreciation"
    DISPOSAL = "DISPOSAL", "Disposal"
    MAINTENANCE = "MAINTENANCE", "Maintenance"
    ASSIGNMENT = "ASSIGNMENT", "Assignment"
    TRANSFER = "TRANSFER", "Transfer"
    EVIDENCE = "EVIDENCE", "Evidence"


ACTIVE_FINDING_STATUSES = (FindingStatus.OPEN, FindingStatus.UNDER_REVIEW)
TERMINAL_FINDING_STATUSES = (
    FindingStatus.RESOLVED,
    FindingStatus.ACCEPTED,
    FindingStatus.REJECTED,
)


class AssuranceHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Assurance records must be changed through transactional services.")

    def delete(self):
        raise ValidationError("Assurance history cannot be deleted.")


class AssuranceRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="assurance_runs"
    )
    run_type = models.CharField(max_length=12, choices=AssuranceRunType.choices)
    status = models.CharField(
        max_length=12, choices=AssuranceRunStatus.choices, default=AssuranceRunStatus.PENDING
    )
    verification_campaign = models.ForeignKey(
        "verification.VerificationCampaign",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assurance_runs",
    )
    stale_after_days = models.PositiveSmallIntegerField(default=365)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assurance_runs_started",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assurance_runs_completed",
    )
    assets_evaluated = models.PositiveIntegerField(default=0)
    findings_generated = models.PositiveIntegerField(default=0)
    findings_open = models.PositiveIntegerField(default=0)
    findings_resolved = models.PositiveIntegerField(default=0)
    failure_message = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = AssuranceHistoryQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(run_type__in=AssuranceRunType.values), name="assurance_run_type_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=AssuranceRunStatus.values),
                name="assurance_run_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(stale_after_days__gt=0), name="assurance_stale_days_positive"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=AssuranceRunStatus.PENDING,
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                    )
                    | Q(
                        status=AssuranceRunStatus.RUNNING,
                        started_at__isnull=False,
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                    )
                    | Q(
                        status__in=(AssuranceRunStatus.COMPLETED, AssuranceRunStatus.FAILED),
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        completed_by__isnull=False,
                    )
                    | Q(
                        status=AssuranceRunStatus.CANCELLED,
                        completed_at__isnull=False,
                        completed_by__isnull=False,
                    )
                ),
                name="assurance_run_timestamps_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "status", "created_at"), name="assrun_org_state_idx"
            ),
            models.Index(
                fields=("organization", "run_type", "started_at"), name="assrun_org_type_idx"
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.started_by_id and self.started_by.organization_id != self.organization_id:
            errors["started_by"] = "Run actor must belong to the run organization."
        if self.completed_by_id and self.completed_by.organization_id != self.organization_id:
            errors["completed_by"] = "Run actor must belong to the run organization."
        if (
            self.verification_campaign_id
            and self.verification_campaign.organization_id != self.organization_id
        ):
            errors["verification_campaign"] = "Campaign must belong to the run organization."
        if self.run_type == AssuranceRunType.PHYSICAL and not self.verification_campaign_id:
            errors["verification_campaign"] = "Physical runs require a verification campaign."
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        raise ValidationError("Assurance runs are retained as audit history.")

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status in (
                AssuranceRunStatus.COMPLETED,
                AssuranceRunStatus.FAILED,
                AssuranceRunStatus.CANCELLED,
            ):
                if any(
                    field.name not in {"id", "updated_at"}
                    and getattr(previous, field.attname) != getattr(self, field.attname)
                    for field in self._meta.concrete_fields
                ):
                    raise ValidationError("Terminal assurance run history is immutable.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.run_type} assurance run ({self.status})"


class AssuranceFinding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="assurance_findings"
    )
    assurance_run = models.ForeignKey(
        AssuranceRun, on_delete=models.PROTECT, related_name="findings"
    )
    last_detected_run = models.ForeignKey(
        AssuranceRun, on_delete=models.PROTECT, related_name="findings_last_detected"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assurance_findings",
    )
    physical_verification = models.ForeignKey(
        "verification.PhysicalVerification",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assurance_findings",
    )
    identity_key = models.CharField(max_length=80)
    finding_type = models.CharField(max_length=40, choices=FindingType.choices)
    severity = models.CharField(max_length=8, choices=FindingSeverity.choices)
    status = models.CharField(
        max_length=16, choices=FindingStatus.choices, default=FindingStatus.OPEN
    )
    source = models.CharField(max_length=24, choices=FindingSource.choices)
    expected_value = models.TextField(blank=True)
    observed_value = models.TextField(blank=True)
    description = models.TextField()
    occurrence_count = models.PositiveIntegerField(default=1)
    first_detected_at = models.DateTimeField(default=timezone.now)
    last_detected_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assurance_findings_resolved",
    )
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = AssuranceHistoryQuerySet.as_manager()

    class Meta:
        ordering = ("-last_detected_at", "asset__asset_tag")
        constraints = [
            models.CheckConstraint(
                condition=Q(finding_type__in=FindingType.values),
                name="assfinding_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(severity__in=FindingSeverity.values),
                name="assfinding_severity_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=FindingStatus.values), name="assfinding_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(source__in=FindingSource.values), name="assfinding_source_valid"
            ),
            models.CheckConstraint(
                condition=Q(occurrence_count__gte=1), name="assfinding_occurrences_positive"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=ACTIVE_FINDING_STATUSES,
                        resolved_at__isnull=True,
                        resolved_by__isnull=True,
                    )
                    | Q(
                        status__in=TERMINAL_FINDING_STATUSES,
                        resolved_at__isnull=False,
                        resolved_by__isnull=False,
                    )
                ),
                name="assfinding_resolution_valid",
            ),
            models.UniqueConstraint(
                fields=("organization", "identity_key", "finding_type"),
                condition=Q(status__in=ACTIVE_FINDING_STATUSES),
                name="assfinding_active_identity_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "status", "severity"), name="assfind_org_state_idx"
            ),
            models.Index(
                fields=("organization", "asset", "finding_type"), name="assfind_org_asset_idx"
            ),
            models.Index(
                fields=("organization", "assurance_run", "status"),
                name="assfind_org_run_idx",
            ),
            models.Index(
                fields=("organization", "source", "finding_type"), name="assfind_org_src_idx"
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.asset_id and self.asset.organization_id != self.organization_id:
            errors["asset"] = "Asset must belong to the finding organization."
        if (
            self.physical_verification_id
            and self.physical_verification.organization_id != self.organization_id
        ):
            errors["physical_verification"] = (
                "Physical verification must belong to the finding organization."
            )
        if not self.asset_id and not self.physical_verification_id:
            errors["asset"] = "Findings require an asset or a physical observation."
        if (
            self.asset_id
            and self.physical_verification_id
            and self.physical_verification.asset_id != self.asset_id
        ):
            errors["physical_verification"] = (
                "The observation must refer to the selected registered asset."
            )
        for field in ("assurance_run", "last_detected_run"):
            related = getattr(self, field, None)
            if related and related.organization_id != self.organization_id:
                errors[field] = "Run must belong to the finding organization."
        if self.resolved_by_id and self.resolved_by.organization_id != self.organization_id:
            errors["resolved_by"] = "Reviewer must belong to the finding organization."
        if self.assurance_run_id and self.identity_key and self.asset_id:
            if self.identity_key != f"asset:{self.asset_id}":
                errors["identity_key"] = "Asset finding identity must match its asset."
        if not self.asset_id and self.physical_verification_id and self.identity_key:
            if self.identity_key != f"physical:{self.physical_verification_id}":
                errors["identity_key"] = "Observation finding identity must match its observation."
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        raise ValidationError("Assurance findings are retained as audit history.")

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status in TERMINAL_FINDING_STATUSES:
                if any(
                    field.name not in {"id", "updated_at"}
                    and getattr(previous, field.attname) != getattr(self, field.attname)
                    for field in self._meta.concrete_fields
                ):
                    raise ValidationError("Terminal assurance finding history is immutable.")
        super().save(*args, **kwargs)

    def __str__(self):
        subject = self.asset.asset_tag if self.asset_id else "Unregistered physical item"
        return f"{self.finding_type}: {subject} ({self.status})"


class AssuranceFindingOccurrence(models.Model):
    """Immutable snapshot proving a finding was detected during a particular run."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="assurance_occurrences"
    )
    finding = models.ForeignKey(
        AssuranceFinding, on_delete=models.PROTECT, related_name="occurrences"
    )
    assurance_run = models.ForeignKey(
        AssuranceRun, on_delete=models.PROTECT, related_name="finding_occurrences"
    )
    detected_at = models.DateTimeField(default=timezone.now)
    expected_value = models.TextField(blank=True)
    observed_value = models.TextField(blank=True)
    description = models.TextField()
    objects = AssuranceHistoryQuerySet.as_manager()

    class Meta:
        ordering = ("detected_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("finding", "assurance_run"), name="assfinding_run_occurrence_uniq"
            )
        ]
        indexes = [
            models.Index(
                fields=("organization", "assurance_run", "detected_at"),
                name="assocc_org_run_idx",
            )
        ]

    def clean(self):
        super().clean()
        if self.finding_id and self.finding.organization_id != self.organization_id:
            raise ValidationError("Finding and occurrence must share an organization.")
        if self.assurance_run_id and self.assurance_run.organization_id != self.organization_id:
            raise ValidationError("Run and occurrence must share an organization.")

    def delete(self, *args, **kwargs):
        raise ValidationError("Finding occurrence history cannot be deleted.")

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and type(self).objects.filter(pk=self.pk).exists():
            previous = type(self).objects.get(pk=self.pk)
            if any(
                field.name not in {"id"}
                and getattr(previous, field.attname) != getattr(self, field.attname)
                for field in self._meta.concrete_fields
            ):
                raise ValidationError("Finding occurrence history is immutable.")
        super().save(*args, **kwargs)
