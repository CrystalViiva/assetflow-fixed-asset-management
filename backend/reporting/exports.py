"""Durable rendering of immutable report snapshot rows."""

import csv
import hashlib
import json
import tempfile
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.core.files.storage import storages
from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.services import record_event
from reporting.export_schemas import EXPORT_SCHEMA_VERSION, schema_for
from reporting.models import (
    ExportFormat,
    ExportStatus,
    ReportExport,
    ReportSnapshot,
    ReportSnapshotRow,
    SnapshotStatus,
)
from reporting.selectors import snapshots_for_user


class ExportGenerationError(Exception):
    """The requested immutable snapshot could not be rendered safely."""


class ExportAttemptError(Exception):
    """Generation failed for one fenced attempt; Celery may safely retry it."""

    def __init__(self, attempt_token, cause):
        self.attempt_token = attempt_token
        self.cause = cause
        super().__init__(f"Export attempt failed: {type(cause).__name__}")


def request_export(*, user, snapshot_id, export_format, idempotency_key, ip_address=None):
    try:
        snapshot = snapshots_for_user(user).get(pk=snapshot_id)
    except (ReportSnapshot.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("Report snapshot is outside your scope.") from exc
    if snapshot.status != SnapshotStatus.COMPLETED:
        raise ValidationError({"source_snapshot": "Exports require a completed report snapshot."})
    try:
        schema_for(snapshot)
    except ValueError as exc:
        raise ValidationError({"source_snapshot": str(exc)}) from exc
    if export_format not in ExportFormat.values:
        raise ValidationError({"format": "Unsupported export format."})
    existing = ReportExport.objects.filter(
        organization_id=user.organization_id, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.source_snapshot_id != snapshot.pk or existing.format != export_format:
            raise ValidationError(
                {"idempotency_key": "This key was used for different export parameters."}
            )
        if existing.status == ExportStatus.QUEUED:
            transaction.on_commit(lambda: _enqueue_export(existing.pk))
        return existing, False
    retention = settings.REPORT_EXPORT_RETENTION_DAYS
    if retention < 1:
        raise ValidationError("Export retention must be at least one day.")
    try:
        with transaction.atomic():
            export = ReportExport.objects.create(
                organization_id=user.organization_id,
                requested_by=user,
                source_snapshot=snapshot,
                format=export_format,
                idempotency_key=idempotency_key,
                schema_version=EXPORT_SCHEMA_VERSION,
                expires_at=timezone.now() + timedelta(days=retention),
            )
            record_event(
                organization=user.organization,
                user=user,
                ip_address=ip_address,
                action="REPORT_EXPORT_REQUESTED",
                entity_type="REPORT_EXPORT",
                entity_id=export.pk,
                metadata={"snapshot_id": str(snapshot.pk), "format": export_format},
            )
            transaction.on_commit(lambda: _enqueue_export(export.pk))
        return export, True
    except IntegrityError as exc:
        existing = ReportExport.objects.get(
            organization_id=user.organization_id, idempotency_key=idempotency_key
        )
        if existing.source_snapshot_id != snapshot.pk or existing.format != export_format:
            raise ValidationError(
                {"idempotency_key": "This key was used for different export parameters."}
            ) from exc
        return existing, False


def _enqueue_export(export_id):
    from reporting.tasks import generate_report_export

    generate_report_export.delay(str(export_id))


def execute_export(*, export_id, actor=None):
    """Claim, render/store outside transactions, then publish through a fenced commit."""
    attempt_token = uuid4()
    with transaction.atomic():
        try:
            export = (
                ReportExport.objects.select_for_update()
                .select_related("organization", "requested_by", "source_snapshot")
                .get(pk=export_id)
            )
        except ReportExport.DoesNotExist:
            return None
        if export.status in (ExportStatus.COMPLETED, ExportStatus.FAILED, ExportStatus.EXPIRED):
            return export
        if export.status == ExportStatus.RUNNING:
            # Fresh RUNNING rows belong to another delivery. Recovery resets
            # abandoned claims after the worker-loss grace period.
            return export
        if export.expires_at <= timezone.now():
            export.status = ExportStatus.FAILED
            export.failed_at = timezone.now()
            export.failure_class = "ExportExpired"
            export.failure_message = "Export expired before generation completed."
            if export.generation_token:
                export.cleanup_storage_keys = _with_cleanup_key(
                    export.cleanup_storage_keys,
                    _export_storage_key(export, export.generation_token),
                )
            export.save(
                update_fields=(
                    "status",
                    "failed_at",
                    "failure_class",
                    "failure_message",
                    "cleanup_storage_keys",
                    "updated_at",
                )
            )
            record_event(
                organization=export.organization,
                user=None,
                action="REPORT_EXPORT_FAILED",
                entity_type="REPORT_EXPORT",
                entity_id=export.pk,
                metadata={"failure_class": export.failure_class},
            )
            return export
        if export.source_snapshot.status != SnapshotStatus.COMPLETED:
            raise ExportGenerationError("Source snapshot is no longer available.")
        if export.generation_token:
            export.cleanup_storage_keys = _with_cleanup_key(
                export.cleanup_storage_keys,
                _export_storage_key(export, export.generation_token),
            )
        export.status = ExportStatus.RUNNING
        export.generation_token = attempt_token
        export.started_at = timezone.now()
        export.failure_class = ""
        export.failure_message = ""
        export.save(
            update_fields=(
                "status",
                "generation_token",
                "cleanup_storage_keys",
                "started_at",
                "failure_class",
                "failure_message",
                "updated_at",
            )
        )

    key = ""
    stored_key = ""
    output = None
    try:
        # Rendering and all storage operations run in autocommit mode. The
        # completed snapshot rows are immutable, and RUNNING is not downloadable.
        fields = schema_for(export.source_snapshot)
        if export.schema_version != EXPORT_SCHEMA_VERSION:
            raise ExportGenerationError("Unsupported export schema version.")
        output, row_count, byte_size, digest = _render_export(export, fields)
        if row_count != export.source_snapshot.row_count:
            raise ExportGenerationError("Snapshot row count does not match its captured metadata.")
        key = _export_storage_key(export, attempt_token)
        storage = storages["assetflow_private"]
        output.seek(0)
        stored_key = storage.save(key, File(output, name=key.rsplit("/", 1)[-1]))
        _verify_export_storage(storage, stored_key, byte_size, digest)

        published = False
        expired = False
        with transaction.atomic():
            current = (
                ReportExport.objects.select_for_update()
                .select_related("organization", "source_snapshot")
                .get(pk=export_id)
            )
            if current.status == ExportStatus.RUNNING and current.generation_token == attempt_token:
                if current.expires_at <= timezone.now():
                    current.status = ExportStatus.FAILED
                    current.failed_at = timezone.now()
                    current.failure_class = "ExportExpired"
                    current.failure_message = "Export expired before generation completed."
                    current.cleanup_storage_keys = _with_cleanup_key(
                        current.cleanup_storage_keys, stored_key
                    )
                    current.save(
                        update_fields=(
                            "status",
                            "failed_at",
                            "failure_class",
                            "failure_message",
                            "cleanup_storage_keys",
                            "updated_at",
                        )
                    )
                    record_event(
                        organization=current.organization,
                        user=None,
                        action="REPORT_EXPORT_FAILED",
                        entity_type="REPORT_EXPORT",
                        entity_id=current.pk,
                        metadata={"failure_class": current.failure_class},
                    )
                    expired = True
                else:
                    current.status = ExportStatus.COMPLETED
                    current.generation_token = None
                    current.completed_at = timezone.now()
                    current.storage_key = stored_key
                    current.row_count = row_count
                    current.byte_size = byte_size
                    current.sha256 = digest
                    current.cleanup_storage_keys = [
                        cleanup_key
                        for cleanup_key in current.cleanup_storage_keys
                        if cleanup_key != stored_key
                    ]
                    current.save(
                        update_fields=(
                            "status",
                            "generation_token",
                            "completed_at",
                            "storage_key",
                            "row_count",
                            "byte_size",
                            "sha256",
                            "cleanup_storage_keys",
                            "updated_at",
                        )
                    )
                    record_event(
                        organization=current.organization,
                        user=actor,
                        action="REPORT_EXPORT_COMPLETED",
                        entity_type="REPORT_EXPORT",
                        entity_id=current.pk,
                        metadata={
                            "byte_size": byte_size,
                            "sha256": digest,
                            "row_count": row_count,
                        },
                    )
                    published = True

        if not published:
            _delete_export_key(stored_key)
            if expired:
                return current
            return current
        return current
    except Exception as exc:
        cleanup_key = stored_key or key
        if cleanup_key:
            _delete_export_key(cleanup_key)
        with transaction.atomic():
            current = ReportExport.objects.select_for_update().get(pk=export_id)
            if current.status == ExportStatus.RUNNING and current.generation_token == attempt_token:
                current.status = ExportStatus.QUEUED
                current.started_at = None
                if cleanup_key:
                    current.cleanup_storage_keys = _with_cleanup_key(
                        current.cleanup_storage_keys, cleanup_key
                    )
                current.save(
                    update_fields=("status", "started_at", "cleanup_storage_keys", "updated_at")
                )
        raise ExportAttemptError(attempt_token, exc) from exc
    finally:
        if output is not None:
            output.close()


def _render_export(export, fields):
    output = tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024, mode="w+b")
    count = 0
    maximum = settings.REPORT_EXPORT_MAX_BYTES
    if maximum < 1:
        output.close()
        raise ExportGenerationError("Export size limit is not configured correctly.")

    def write(text):
        data = text.encode("utf-8")
        if output.tell() + len(data) > maximum:
            raise ExportGenerationError("Export exceeds the configured size limit.")
        output.write(data)

    if export.format == ExportFormat.CSV:
        text = tempfile.SpooledTemporaryFile(
            max_size=2 * 1024 * 1024, mode="w+", encoding="utf-8", newline=""
        )
        writer = csv.writer(text, lineterminator="\r\n")
        writer.writerow([field.name for field in fields])
        for row in (
            ReportSnapshotRow.objects.filter(snapshot=export.source_snapshot)
            .order_by("ordinal")
            .iterator(chunk_size=500)
        ):
            writer.writerow(
                [_csv_value(row.payload.get(field.name), field.kind) for field in fields]
            )
            count += 1
            if text.tell() > maximum:
                raise ExportGenerationError("Export exceeds the configured size limit.")
        text.seek(0)
        while chunk := text.read(1024 * 1024):
            write(chunk)
        text.close()
    elif export.format == ExportFormat.JSON:
        envelope = {
            "schema_version": export.schema_version,
            "snapshot": {
                "id": str(export.source_snapshot_id),
                "report_type": export.source_snapshot.report_type,
                "schema_version": export.source_snapshot.schema_version,
                "as_of": export.source_snapshot.as_of.isoformat(),
                "generated_at": export.source_snapshot.generated_at.isoformat(),
            },
            "columns": [field.name for field in fields],
        }
        write(json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))[:-1])
        write(',"rows":[')
        first = True
        for row in (
            ReportSnapshotRow.objects.filter(snapshot=export.source_snapshot)
            .order_by("ordinal")
            .iterator(chunk_size=500)
        ):
            if not first:
                write(",")
            first = False
            payload = {field.name: row.payload.get(field.name) for field in fields}
            _write_json_row(write, payload, fields)
            count += 1
        write("]}")
    else:
        raise ExportGenerationError("Unsupported export format.")
    output.seek(0)
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: output.read(1024 * 1024), b""):
        size += len(chunk)
        digest.update(chunk)
    output.seek(0)
    return output, count, size, digest.hexdigest()


def _write_json_row(write, payload, fields):
    encoder = json.JSONEncoder(ensure_ascii=False, separators=(",", ":"))
    write("{")
    for index, field in enumerate(fields):
        if index:
            write(",")
        write(json.dumps(field.name, ensure_ascii=False))
        write(":")
        value = payload[field.name]
        if isinstance(value, str):
            write('"')
            for offset in range(0, len(value), 32 * 1024):
                escaped = json.dumps(value[offset : offset + 32 * 1024], ensure_ascii=False)
                write(escaped[1:-1])
            write('"')
        else:
            for piece in encoder.iterencode(value):
                write(piece)
    write("}")


def _csv_value(value, kind):
    if value is None:
        return ""
    text = str(value)
    if kind in {"text", "json"} and text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _verify_export_storage(storage, key, expected_size, expected_digest):
    digest = hashlib.sha256()
    size = 0
    with storage.open(key, "rb") as stored:
        for chunk in iter(lambda: stored.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    if size != expected_size or digest.hexdigest() != expected_digest:
        raise ExportGenerationError("Stored export failed integrity verification.")


def open_export(*, export):
    if export.status != ExportStatus.COMPLETED or export.expires_at <= timezone.now():
        raise PermissionDenied("Export is unavailable.")
    stream = tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024, mode="w+b")
    digest = hashlib.sha256()
    size = 0
    try:
        with storages["assetflow_private"].open(export.storage_key, "rb") as stored:
            for chunk in iter(lambda: stored.read(1024 * 1024), b""):
                stream.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size != export.byte_size or digest.hexdigest() != export.sha256:
            raise ExportGenerationError("Stored export failed integrity verification.")
        stream.seek(0)
        return stream
    except Exception as exc:
        stream.close()
        raise ExportGenerationError("Export artifact is unavailable or corrupt.") from exc


def recover_exports(*, older_than=timedelta(minutes=35), limit=100):
    cutoff = timezone.now() - older_than
    ids = list(
        ReportExport.objects.filter(
            status__in=(ExportStatus.QUEUED, ExportStatus.RUNNING), updated_at__lt=cutoff
        )
        .order_by("updated_at", "pk")
        .values_list("pk", flat=True)[:limit]
    )
    for export_id in ids:
        with transaction.atomic():
            export = ReportExport.objects.select_for_update().get(pk=export_id)
            if (
                export.status not in (ExportStatus.QUEUED, ExportStatus.RUNNING)
                or export.updated_at >= cutoff
            ):
                continue
            if export.status == ExportStatus.RUNNING and export.generation_token:
                export.cleanup_storage_keys = _with_cleanup_key(
                    export.cleanup_storage_keys,
                    _export_storage_key(export, export.generation_token),
                )
            export.status = ExportStatus.QUEUED
            export.started_at = None
            export.save(
                update_fields=("status", "started_at", "cleanup_storage_keys", "updated_at")
            )
            transaction.on_commit(lambda value=export.pk: _enqueue_export(value))
    return len(ids)


def expire_exports(*, limit=500):
    now = timezone.now()
    expired = 0
    ids = list(
        ReportExport.objects.filter(status=ExportStatus.COMPLETED, expires_at__lte=now).values_list(
            "pk", flat=True
        )[:limit]
    )
    for export_id in ids:
        with transaction.atomic():
            export = ReportExport.objects.select_for_update().get(pk=export_id)
            if export.status != ExportStatus.COMPLETED or export.expires_at > now:
                continue
            export.status = ExportStatus.EXPIRED
            export.expired_at = now
            export.save(update_fields=("status", "expired_at", "updated_at"))
            record_event(
                organization=export.organization,
                user=None,
                action="REPORT_EXPORT_EXPIRED",
                entity_type="REPORT_EXPORT",
                entity_id=export.pk,
                metadata={},
            )
            transaction.on_commit(lambda key=export.storage_key: _delete_export_key(key))
            expired += 1
    # Retry physical deletes for expired artifacts. Database expiry already gates access.
    for export in ReportExport.objects.filter(status=ExportStatus.EXPIRED).exclude(storage_key="")[
        :limit
    ]:
        if _delete_export_key(export.storage_key):
            export.storage_key = ""
            export.save(update_fields=("storage_key", "updated_at"))
    return expired


def _delete_export_key(key):
    if key:
        try:
            storages["assetflow_private"].delete(key)
        except Exception:
            return False
    return True


def _export_storage_key(export, attempt_token):
    return (
        f"exports/{export.organization_id}/{export.pk}/attempts/"
        f"{attempt_token.hex}/{export.format.lower()}"
    )


def _with_cleanup_key(keys, key):
    return list(dict.fromkeys([*keys, key])) if key else list(keys)


def fail_export(*, export_id, exc, attempt_token=None):
    with transaction.atomic():
        export = ReportExport.objects.select_for_update().get(pk=export_id)
        if export.status in (ExportStatus.COMPLETED, ExportStatus.EXPIRED, ExportStatus.FAILED):
            return export
        if attempt_token is not None and export.generation_token != attempt_token:
            return export
        export.status = ExportStatus.FAILED
        export.failed_at = timezone.now()
        export.failure_class = type(exc).__name__[:100]
        export.failure_message = "Export generation failed after retries."
        if export.generation_token:
            export.cleanup_storage_keys = _with_cleanup_key(
                export.cleanup_storage_keys,
                _export_storage_key(export, export.generation_token),
            )
        export.storage_key = ""
        export.byte_size = None
        export.sha256 = ""
        export.save(
            update_fields=(
                "status",
                "failed_at",
                "failure_class",
                "failure_message",
                "storage_key",
                "byte_size",
                "sha256",
                "cleanup_storage_keys",
                "updated_at",
            )
        )
        record_event(
            organization=export.organization,
            user=None,
            action="REPORT_EXPORT_FAILED",
            entity_type="REPORT_EXPORT",
            entity_id=export.pk,
            metadata={"failure_class": export.failure_class},
        )
        transaction.on_commit(lambda: cleanup_failed_exports(export_id=export.pk))
        return export


def cleanup_failed_exports(*, limit=500, export_id=None):
    """Retry deletion of unpublished attempt objects without touching published keys."""
    queryset = ReportExport.objects.exclude(cleanup_storage_keys=[])
    if export_id is not None:
        queryset = queryset.filter(pk=export_id)
    for export in queryset.order_by("updated_at", "pk")[:limit]:
        for key in list(export.cleanup_storage_keys):
            if key == export.storage_key:
                continue
            if not _delete_export_key(key):
                continue
            with transaction.atomic():
                current = ReportExport.objects.select_for_update().get(pk=export.pk)
                current.cleanup_storage_keys = [
                    item for item in current.cleanup_storage_keys if item != key
                ]
                current.save(update_fields=("cleanup_storage_keys", "updated_at"))
