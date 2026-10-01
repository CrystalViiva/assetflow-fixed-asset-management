"""Durable extraction ownership, publication and watermark metadata."""

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from analytics.contracts import SNAPSHOT_REPORT_TYPES

REPORT_TYPE_CHOICES = tuple((report_type, report_type) for report_type in SNAPSHOT_REPORT_TYPES)


class AnalyticsRunStatus(models.TextChoices):
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    SUPERSEDED = "SUPERSEDED", "Superseded"


class AnalyticsCheckpoint(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="analytics_checkpoints"
    )
    dataset = models.CharField(max_length=64, choices=REPORT_TYPE_CHOICES)
    watermark_at = models.DateTimeField(null=True, blank=True)
    watermark_snapshot_id = models.UUIDField(null=True, blank=True)
    watermark_ordinal = models.PositiveBigIntegerField(default=0)
    generation = models.PositiveBigIntegerField(default=0)
    active_attempt_token = models.UUIDField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "dataset"), name="analytics_checkpoint_tenant_dataset_uniq"
            ),
            models.CheckConstraint(
                condition=Q(dataset__in=SNAPSHOT_REPORT_TYPES),
                name="analytics_checkpoint_dataset_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        watermark_at__isnull=True,
                        watermark_snapshot_id__isnull=True,
                        watermark_ordinal=0,
                    )
                    | Q(watermark_at__isnull=False, watermark_snapshot_id__isnull=False)
                ),
                name="analytics_checkpoint_cursor_valid",
            ),
        ]
        indexes = [models.Index(fields=("dataset", "updated_at"), name="an_checkpoint_updated_idx")]


class AnalyticsRun(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="analytics_runs"
    )
    dataset = models.CharField(max_length=64, choices=REPORT_TYPE_CHOICES)
    run_key = models.CharField(max_length=250)
    status = models.CharField(max_length=12, choices=AnalyticsRunStatus.choices)
    attempt_token = models.UUIDField(default=uuid.uuid4)
    attempt_count = models.PositiveIntegerField(default=1)
    full_refresh = models.BooleanField(default=False)
    source_watermark_at = models.DateTimeField(null=True, blank=True)
    source_watermark_snapshot_id = models.UUIDField(null=True, blank=True)
    source_watermark_ordinal = models.PositiveBigIntegerField(default=0)
    resulting_watermark_at = models.DateTimeField(null=True, blank=True)
    resulting_watermark_snapshot_id = models.UUIDField(null=True, blank=True)
    resulting_watermark_ordinal = models.PositiveBigIntegerField(default=0)
    row_count = models.PositiveBigIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    failure_class = models.CharField(max_length=100, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "dataset", "run_key"),
                name="analytics_run_tenant_dataset_key_uniq",
            ),
            models.CheckConstraint(
                condition=Q(status__in=AnalyticsRunStatus.values), name="analytics_run_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(dataset__in=SNAPSHOT_REPORT_TYPES), name="analytics_run_dataset_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        source_watermark_at__isnull=True,
                        source_watermark_snapshot_id__isnull=True,
                        source_watermark_ordinal=0,
                    )
                    | Q(
                        source_watermark_at__isnull=False,
                        source_watermark_snapshot_id__isnull=False,
                    )
                ),
                name="analytics_run_source_cursor_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        resulting_watermark_at__isnull=True,
                        resulting_watermark_snapshot_id__isnull=True,
                        resulting_watermark_ordinal=0,
                    )
                    | Q(
                        resulting_watermark_at__isnull=False,
                        resulting_watermark_snapshot_id__isnull=False,
                    )
                ),
                name="analytics_run_result_cursor_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=AnalyticsRunStatus.RUNNING, finished_at__isnull=True)
                    | Q(
                        status=AnalyticsRunStatus.COMPLETED,
                        finished_at__isnull=False,
                        failure_class="",
                        failure_message="",
                    )
                    | Q(
                        status=AnalyticsRunStatus.FAILED,
                        finished_at__isnull=False,
                        failure_class__gt="",
                    )
                    | Q(
                        status=AnalyticsRunStatus.SUPERSEDED,
                        finished_at__isnull=False,
                        failure_class="SupersededAttempt",
                    )
                ),
                name="analytics_run_state_consistent",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "dataset", "status"), name="analytics_run_state_idx"
            ),
            models.Index(fields=("started_at", "status"), name="analytics_run_started_idx"),
        ]


class AnalyticsPublication(models.Model):
    run = models.OneToOneField(AnalyticsRun, on_delete=models.PROTECT, related_name="publication")
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="analytics_publications",
    )
    dataset = models.CharField(max_length=64, choices=REPORT_TYPE_CHOICES)
    contract_version = models.PositiveSmallIntegerField()
    storage_key = models.CharField(max_length=512)
    sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveBigIntegerField()
    row_count = models.PositiveBigIntegerField()
    source_watermark_at = models.DateTimeField(null=True, blank=True)
    source_watermark_snapshot_id = models.UUIDField(null=True, blank=True)
    source_watermark_ordinal = models.PositiveBigIntegerField(default=0)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "dataset", "run"),
                name="analytics_pub_tenant_dataset_run_uniq",
            ),
            models.CheckConstraint(
                condition=Q(contract_version__gt=0), name="analytics_publication_contract_positive"
            ),
            models.CheckConstraint(
                condition=Q(dataset__in=SNAPSHOT_REPORT_TYPES), name="analytics_pub_dataset_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        source_watermark_at__isnull=True,
                        source_watermark_snapshot_id__isnull=True,
                        source_watermark_ordinal=0,
                    )
                    | Q(
                        source_watermark_at__isnull=False,
                        source_watermark_snapshot_id__isnull=False,
                    )
                ),
                name="analytics_pub_cursor_valid",
            ),
            models.CheckConstraint(condition=Q(storage_key__gt=""), name="analytics_pub_key_valid"),
            models.CheckConstraint(
                condition=Q(sha256__regex=r"^[0-9a-f]{64}$"),
                name="analytics_publication_hash_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "dataset", "published_at"), name="analytics_pub_tenant_idx"
            )
        ]


class CuratedRunStatus(models.TextChoices):
    RUNNING = "RUNNING", "Running"
    FAILED = "FAILED", "Failed"
    COMPLETED = "COMPLETED", "Completed"


class CuratedProcessingRun(models.Model):
    """Fenced transformation attempt for one tenant and immutable source set."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="curated_runs"
    )
    processing_key = models.CharField(max_length=64)
    contract_version = models.PositiveSmallIntegerField()
    transform_version = models.PositiveSmallIntegerField()
    source_publications = models.JSONField()
    status = models.CharField(max_length=12, choices=CuratedRunStatus.choices)
    attempt_token = models.UUIDField(default=uuid.uuid4)
    attempt_count = models.PositiveIntegerField(default=1)
    input_manifest_key = models.CharField(max_length=512, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    failure_class = models.CharField(max_length=100, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "processing_key"), name="curated_run_org_key_uniq"
            ),
            models.CheckConstraint(condition=Q(contract_version=1), name="curated_run_contract_v1"),
            models.CheckConstraint(
                condition=Q(transform_version=1), name="curated_run_transform_v1"
            ),
            models.CheckConstraint(
                condition=Q(status__in=CuratedRunStatus.values), name="curated_run_status_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=CuratedRunStatus.RUNNING, finished_at__isnull=True)
                    | Q(
                        status=CuratedRunStatus.FAILED,
                        finished_at__isnull=False,
                        failure_class__gt="",
                    )
                    | Q(
                        status=CuratedRunStatus.COMPLETED,
                        finished_at__isnull=False,
                        failure_class="",
                        failure_message="",
                    )
                ),
                name="curated_run_state_consistent",
            ),
            models.CheckConstraint(
                condition=Q(processing_key__regex=r"^[0-9a-f]{64}$"),
                name="curated_run_key_sha256",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "status"), name="curated_run_org_status_idx"),
            models.Index(fields=("started_at", "status"), name="curated_run_started_idx"),
        ]


class CuratedPublication(models.Model):
    """Consumer-visible pointer to a fully validated set of tenant Parquet outputs."""

    run = models.OneToOneField(
        CuratedProcessingRun, on_delete=models.PROTECT, related_name="publication"
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="curated_publications"
    )
    manifest_key = models.CharField(max_length=512)
    manifest_sha256 = models.CharField(max_length=64)
    manifest_byte_size = models.PositiveBigIntegerField()
    datasets = models.JSONField()
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "run"), name="curated_pub_org_run_uniq"
            ),
            models.CheckConstraint(
                condition=Q(manifest_key__gt=""), name="curated_pub_manifest_key_valid"
            ),
            models.CheckConstraint(
                condition=Q(manifest_sha256__regex=r"^[0-9a-f]{64}$"),
                name="curated_pub_manifest_hash_valid",
            ),
        ]
