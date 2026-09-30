"""Durable, organization-scoped report snapshot metadata and rows."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserRole


class SnapshotStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class ReportType(models.TextChoices):
    ASSET_REGISTER = "asset_register", "Asset register"
    ACQUISITIONS = "acquisitions", "Acquisitions and capitalization"
    DEPRECIATION = "depreciation", "Depreciation ledger"
    ACCOUNTING_PERIODS = "accounting_periods", "Accounting periods"
    ASSIGNMENTS = "assignments", "Assignments and custody"
    TRANSFERS = "transfers", "Transfers"
    WORK_ORDERS = "work_orders", "Maintenance work orders"
    MAINTENANCE_COSTS = "maintenance_costs", "Maintenance costs"
    MAINTENANCE_RECORDS = "maintenance_records", "Maintenance records"
    DISPOSALS = "disposals", "Disposals"
    VERIFICATION_CAMPAIGNS = "verification_campaigns", "Physical verification campaigns"
    VERIFICATION_RECORDS = "verification_records", "Physical verification observations"
    VERIFICATION_EXCEPTIONS = "verification_exceptions", "Physical verification exceptions"
    ASSURANCE_RUNS = "assurance_runs", "Assurance runs"
    ASSURANCE_FINDINGS = "assurance_findings", "Assurance findings"
    ASSURANCE_OCCURRENCES = "assurance_occurrences", "Assurance finding occurrences"
    LIFECYCLE_HISTORY = "lifecycle_history", "Lifecycle audit history"


class ImmutableReportSnapshotRowQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Snapshot rows are immutable.")

    def delete(self):
        raise ValidationError("Snapshot rows are immutable.")


class ReportSnapshot(models.Model):
    """One immutable capture request; a repeated key returns this same record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="report_snapshots"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="report_snapshots_requested",
    )
    requested_role = models.CharField(max_length=32, choices=UserRole.choices)
    report_type = models.CharField(max_length=32, choices=ReportType.choices)
    idempotency_key = models.UUIDField()
    parameters = models.JSONField(default=dict)
    scope_department_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=SnapshotStatus.choices, default=SnapshotStatus.QUEUED
    )
    requested_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    as_of = models.DateTimeField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    row_count = models.PositiveBigIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    schema_version = models.PositiveSmallIntegerField(default=1)
    failure_class = models.CharField(max_length=100, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-requested_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "idempotency_key"), name="report_org_idempotency_uniq"
            ),
            models.CheckConstraint(
                condition=Q(report_type__in=ReportType.values), name="report_type_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=SnapshotStatus.values), name="report_status_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=SnapshotStatus.QUEUED,
                        started_at__isnull=True,
                        as_of__isnull=True,
                        generated_at__isnull=True,
                        failed_at__isnull=True,
                    )
                    | Q(
                        status=SnapshotStatus.RUNNING,
                        started_at__isnull=False,
                        generated_at__isnull=True,
                        failed_at__isnull=True,
                    )
                    | Q(
                        status=SnapshotStatus.COMPLETED,
                        started_at__isnull=False,
                        as_of__isnull=False,
                        generated_at__isnull=False,
                        failed_at__isnull=True,
                        failure_class="",
                    )
                    | Q(
                        status=SnapshotStatus.FAILED,
                        generated_at__isnull=True,
                        failed_at__isnull=False,
                        failure_class__gt="",
                    )
                ),
                name="report_status_timestamps_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "report_type", "requested_at"),
                name="report_org_type_idx",
            ),
            models.Index(
                fields=("organization", "status", "requested_at"),
                name="report_org_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.report_type} snapshot {self.pk} ({self.status})"


class ReportSnapshotRow(models.Model):
    """A bounded-schema row, stored separately so snapshots are not one giant JSON value."""

    snapshot = models.ForeignKey(ReportSnapshot, on_delete=models.CASCADE, related_name="rows")
    ordinal = models.PositiveBigIntegerField()
    source_id = models.CharField(max_length=64)
    payload = models.JSONField()
    objects = ImmutableReportSnapshotRowQuerySet.as_manager()

    class Meta:
        ordering = ("ordinal",)
        constraints = [
            models.UniqueConstraint(fields=("snapshot", "ordinal"), name="report_row_ordinal_uniq"),
            models.UniqueConstraint(
                fields=("snapshot", "source_id"), name="report_row_source_uniq"
            ),
        ]
        indexes = [models.Index(fields=("snapshot", "ordinal"), name="report_row_page_idx")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Snapshot rows are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Snapshot rows are immutable.")
