"""Stream completed report snapshots to immutable, attempt-fenced JSONL outputs."""

import hashlib
import json
import logging
import tempfile
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from django.conf import settings
from django.core.files import File
from django.core.files.storage import storages
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from analytics.contracts import CONTRACT_VERSION, ENVELOPE_FIELDS, SNAPSHOT_REPORT_TYPES
from analytics.models import (
    AnalyticsCheckpoint,
    AnalyticsPublication,
    AnalyticsRun,
    AnalyticsRunStatus,
)
from reporting.export_schemas import schema_for
from reporting.models import ReportSnapshot, ReportSnapshotRow, SnapshotStatus

logger = logging.getLogger(__name__)
OUTPUT_CHUNK_SIZE = 500
MAX_RECORDS_PER_RUN = 100_000
MAX_OUTPUT_BYTES = 250 * 1024 * 1024


class AnalyticsExtractionError(Exception):
    """A source or output did not satisfy the versioned extraction contract."""


class StaleAnalyticsAttempt(AnalyticsExtractionError):
    """A newer attempt took ownership before this attempt could publish."""


def _validate_report_type(report_type):
    if report_type not in SNAPSHOT_REPORT_TYPES:
        raise AnalyticsExtractionError("Unknown report snapshot dataset.")


def _cursor_tuple(at, snapshot_id, ordinal):
    if at is None or snapshot_id is None:
        return None
    return at, str(snapshot_id), int(ordinal)


def _json_value(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise AnalyticsExtractionError(f"Unsupported analytics value type: {type(value).__name__}")


def _run_queryset(organization_id, report_type):
    return ReportSnapshot.objects.filter(
        organization_id=organization_id,
        report_type=report_type,
        status=SnapshotStatus.COMPLETED,
        generated_at__isnull=False,
        as_of__isnull=False,
    )


def _source_high_watermark(organization_id, report_type, previous):
    snapshot = _run_queryset(organization_id, report_type).order_by("-generated_at", "-pk").first()
    if snapshot is None:
        return previous
    latest = (snapshot.generated_at, str(snapshot.pk), snapshot.row_count)
    if previous is None:
        return latest
    if latest > previous:
        return latest
    return previous


def _snapshot_queryset(organization_id, report_type, previous, high):
    snapshots = _run_queryset(organization_id, report_type)
    if high is None:
        return snapshots.none()
    high_at, high_id, _ = high
    snapshots = snapshots.filter(
        Q(generated_at__lt=high_at) | Q(generated_at=high_at, pk__lte=high_id)
    )
    if previous is not None:
        overlap = getattr(settings, "ANALYTICS_LATE_ARRIVAL_OVERLAP_HOURS", 48)
        snapshots = snapshots.filter(generated_at__gte=previous[0] - timedelta(hours=overlap))
    return snapshots.order_by("generated_at", "pk")


def _snapshot_records(snapshot, report_type, extracted_at, previous, high):
    dataset = f"{report_type}_snapshots_v{CONTRACT_VERSION}"
    expected_fields = tuple(field.name for field in schema_for(snapshot))
    metadata = {
        "report_type": snapshot.report_type,
        "schema_version": snapshot.schema_version,
        "row_count": snapshot.row_count,
    }
    yield _envelope(
        dataset=dataset,
        snapshot=snapshot,
        extracted_at=extracted_at,
        record_kind="snapshot",
        source_row_id=None,
        ordinal=0,
        logical_record_id=f"{snapshot.pk}:snapshot",
        payload=metadata,
    )

    rows = ReportSnapshotRow.objects.filter(snapshot_id=snapshot.pk).order_by("ordinal")
    actual_rows = 0
    for expected_ordinal, row in enumerate(rows.iterator(chunk_size=OUTPUT_CHUNK_SIZE), start=1):
        actual_rows += 1
        if row.ordinal != expected_ordinal:
            raise AnalyticsExtractionError("Snapshot row ordinals are not contiguous.")
        if set(row.payload) != set(expected_fields):
            raise AnalyticsExtractionError("Snapshot row does not match its frozen schema version.")
        if str(row.payload["id"]) != row.source_id:
            raise AnalyticsExtractionError("Snapshot row identity does not match its source ID.")
        payload = {field: row.payload[field] for field in expected_fields}
        yield _envelope(
            dataset=dataset,
            snapshot=snapshot,
            extracted_at=extracted_at,
            record_kind="row",
            source_row_id=row.source_id,
            ordinal=row.ordinal,
            logical_record_id=f"{snapshot.pk}:row:{row.ordinal}",
            payload=payload,
        )
    if actual_rows != snapshot.row_count:
        raise AnalyticsExtractionError("Completed snapshot row count does not match its metadata.")


def _envelope(
    *,
    dataset,
    snapshot,
    extracted_at,
    record_kind,
    source_row_id,
    ordinal,
    logical_record_id,
    payload,
):
    record = {
        "contract_version": CONTRACT_VERSION,
        "dataset": dataset,
        "organization_id": str(snapshot.organization_id),
        "logical_record_id": logical_record_id,
        "record_kind": record_kind,
        "source_snapshot_id": str(snapshot.pk),
        "source_snapshot_schema_version": snapshot.schema_version,
        "source_row_id": source_row_id,
        "source_ordinal": ordinal,
        "source_as_of": snapshot.as_of.isoformat(),
        "source_generated_at": snapshot.generated_at.isoformat(),
        "extracted_at": extracted_at.isoformat(),
        "payload": _json_value(payload),
    }
    if tuple(record) != ENVELOPE_FIELDS:
        raise AnalyticsExtractionError("Analytics envelope does not match contract version 1.")
    return record


def _records(organization_id, report_type, extracted_at, previous, high):
    snapshots = _snapshot_queryset(organization_id, report_type, previous, high)
    for snapshot in snapshots.iterator(chunk_size=OUTPUT_CHUNK_SIZE):
        yield from _snapshot_records(snapshot, report_type, extracted_at, previous, high)


def _checkpoint(organization_id, report_type):
    checkpoint, _ = AnalyticsCheckpoint.objects.get_or_create(
        organization_id=organization_id, dataset=report_type
    )
    return checkpoint


def _claim(*, organization_id, report_type, run_key, full_refresh=False):
    token = uuid.uuid4()
    with transaction.atomic():
        _checkpoint(organization_id, report_type)
        checkpoint = AnalyticsCheckpoint.objects.select_for_update().get(
            organization_id=organization_id, dataset=report_type
        )
        run, created = AnalyticsRun.objects.get_or_create(
            organization_id=organization_id,
            dataset=report_type,
            run_key=run_key,
            defaults={"status": AnalyticsRunStatus.RUNNING, "attempt_token": token},
        )
        if not created and run.full_refresh != full_refresh:
            raise AnalyticsExtractionError(
                "A run key cannot be reused with a different refresh mode."
            )
        if not created and run.status == AnalyticsRunStatus.COMPLETED:
            return run, checkpoint, None

        if checkpoint.active_attempt_token:
            AnalyticsRun.objects.filter(
                organization_id=organization_id,
                dataset=report_type,
                attempt_token=checkpoint.active_attempt_token,
                status=AnalyticsRunStatus.RUNNING,
            ).exclude(pk=run.pk).update(
                status=AnalyticsRunStatus.SUPERSEDED,
                finished_at=timezone.now(),
                failure_class="SupersededAttempt",
                failure_message="A newer extraction attempt claimed this dataset.",
            )

        run.status = AnalyticsRunStatus.RUNNING
        run.attempt_token = token
        run.attempt_count = 1 if created else run.attempt_count + 1
        run.source_watermark_at = None if full_refresh else checkpoint.watermark_at
        run.source_watermark_snapshot_id = (
            None if full_refresh else checkpoint.watermark_snapshot_id
        )
        run.source_watermark_ordinal = 0 if full_refresh else checkpoint.watermark_ordinal
        run.full_refresh = full_refresh
        run.resulting_watermark_at = None
        run.resulting_watermark_snapshot_id = None
        run.resulting_watermark_ordinal = 0
        run.row_count = 0
        run.started_at = timezone.now()
        run.finished_at = None
        run.failure_class = ""
        run.failure_message = ""
        run.save()

        checkpoint.generation += 1
        checkpoint.active_attempt_token = token
        checkpoint.save(update_fields=("generation", "active_attempt_token", "updated_at"))
        return run, checkpoint, token


def _stage_output(*, organization_id, report_type, token, source_records):
    storage = storages["assetflow_analytics"]
    key = f"staging/{organization_id}/{report_type}/v{CONTRACT_VERSION}/{token}.jsonl"
    digest = hashlib.sha256()
    byte_size = 0
    row_count = 0
    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as buffer:
        for record in source_records:
            raw = (
                json.dumps(
                    record,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            byte_size += len(raw)
            row_count += 1
            if row_count > getattr(settings, "ANALYTICS_MAX_RECORDS_PER_RUN", MAX_RECORDS_PER_RUN):
                raise AnalyticsExtractionError(
                    "Analytics run exceeded the configured record limit."
                )
            if byte_size > getattr(settings, "ANALYTICS_MAX_OUTPUT_BYTES", MAX_OUTPUT_BYTES):
                raise AnalyticsExtractionError("Analytics run exceeded the configured byte limit.")
            buffer.write(raw)
            digest.update(raw)
        buffer.seek(0)
        stored_key = storage.save(key, File(buffer, name=f"{token}.jsonl"))

    verified_digest = hashlib.sha256()
    verified_size = 0
    with storage.open(stored_key, "rb") as staged:
        for chunk in iter(lambda: staged.read(1024 * 1024), b""):
            verified_size += len(chunk)
            verified_digest.update(chunk)
    if verified_size != byte_size or verified_digest.hexdigest() != digest.hexdigest():
        storage.delete(stored_key)
        raise AnalyticsExtractionError("Staged analytics output failed read-back verification.")
    return stored_key, digest.hexdigest(), byte_size, row_count


def _delete_staged(key):
    if not key:
        return
    try:
        storages["assetflow_analytics"].delete(key)
    except Exception:
        logger.exception("Failed to remove an unpublished analytics object.")


def _record_failure(run_id, token, exc):
    with transaction.atomic():
        identity = AnalyticsRun.objects.filter(pk=run_id).values("organization_id", "dataset").get()
        checkpoint = AnalyticsCheckpoint.objects.select_for_update().get(
            organization_id=identity["organization_id"], dataset=identity["dataset"]
        )
        run = AnalyticsRun.objects.select_for_update().get(pk=run_id)
        if run.attempt_token != token or checkpoint.active_attempt_token != token:
            return
        run.status = AnalyticsRunStatus.FAILED
        run.finished_at = timezone.now()
        run.failure_class = type(exc).__name__[:100]
        run.failure_message = "Analytics extraction failed; inspect the sanitized task log."
        run.save(update_fields=("status", "finished_at", "failure_class", "failure_message"))
        checkpoint.active_attempt_token = None
        checkpoint.save(update_fields=("active_attempt_token", "updated_at"))


def _publish(*, run_id, token, checkpoint_id, high, stored_key, digest, byte_size, row_count):
    with transaction.atomic():
        checkpoint = AnalyticsCheckpoint.objects.select_for_update().get(pk=checkpoint_id)
        run = AnalyticsRun.objects.select_for_update().get(pk=run_id)
        if run.attempt_token != token or checkpoint.active_attempt_token != token:
            raise StaleAnalyticsAttempt("A newer attempt owns the dataset checkpoint.")

        high_at, high_snapshot_id, high_ordinal = high if high is not None else (None, None, 0)
        publication = AnalyticsPublication.objects.create(
            run=run,
            organization_id=run.organization_id,
            dataset=run.dataset,
            contract_version=CONTRACT_VERSION,
            storage_key=stored_key,
            sha256=digest,
            byte_size=byte_size,
            row_count=row_count,
            source_watermark_at=high_at,
            source_watermark_snapshot_id=high_snapshot_id,
            source_watermark_ordinal=high_ordinal,
        )
        run.status = AnalyticsRunStatus.COMPLETED
        run.resulting_watermark_at = high_at
        run.resulting_watermark_snapshot_id = high_snapshot_id
        run.resulting_watermark_ordinal = high_ordinal
        run.row_count = row_count
        run.finished_at = timezone.now()
        run.save(
            update_fields=(
                "status",
                "resulting_watermark_at",
                "resulting_watermark_snapshot_id",
                "resulting_watermark_ordinal",
                "row_count",
                "finished_at",
            )
        )
        if high is not None:
            checkpoint.watermark_at = high_at
            checkpoint.watermark_snapshot_id = high_snapshot_id
            checkpoint.watermark_ordinal = high_ordinal
        checkpoint.active_attempt_token = None
        checkpoint.save(
            update_fields=(
                "watermark_at",
                "watermark_snapshot_id",
                "watermark_ordinal",
                "active_attempt_token",
                "updated_at",
            )
        )
        return publication


def extract_report_snapshot_dataset(*, organization_id, report_type, run_key, full_refresh=False):
    """Publish one tenant/report-type JSONL batch for one stable Airflow run key."""
    _validate_report_type(report_type)
    if not run_key or len(run_key) > 250:
        raise AnalyticsExtractionError("A non-empty run key of at most 250 characters is required.")

    run, checkpoint, token = _claim(
        organization_id=organization_id,
        report_type=report_type,
        run_key=run_key,
        full_refresh=full_refresh,
    )
    if token is None:
        return run.publication

    stored_key = ""
    try:
        previous = _cursor_tuple(
            run.source_watermark_at,
            run.source_watermark_snapshot_id,
            run.source_watermark_ordinal,
        )
        current_cursor = _cursor_tuple(
            checkpoint.watermark_at,
            checkpoint.watermark_snapshot_id,
            checkpoint.watermark_ordinal,
        )
        high = _source_high_watermark(organization_id, report_type, current_cursor)
        extracted_at = timezone.now()
        source_records = _records(organization_id, report_type, extracted_at, previous, high)
        stored_key, digest, byte_size, row_count = _stage_output(
            organization_id=organization_id,
            report_type=report_type,
            token=token,
            source_records=source_records,
        )
        return _publish(
            run_id=run.pk,
            token=token,
            checkpoint_id=checkpoint.pk,
            high=high,
            stored_key=stored_key,
            digest=digest,
            byte_size=byte_size,
            row_count=row_count,
        )
    except Exception as exc:
        _delete_staged(stored_key)
        _record_failure(run.pk, token, exc)
        raise


def published_output(publication):
    """Open a published object only by resolving its committed metadata row."""
    return storages["assetflow_analytics"].open(publication.storage_key, "rb")
