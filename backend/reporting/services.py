"""Report snapshot request and generation services."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from audit.services import record_event
from reporting.models import ReportSnapshot, ReportSnapshotRow, SnapshotStatus
from reporting.selectors import (
    report_queryset,
    report_rows,
    report_summary,
    serialize_report_row,
)

MAX_SNAPSHOT_ROWS = 25_000
SNAPSHOT_BATCH_SIZE = 500


class SnapshotTooLarge(Exception):
    """The requested dataset exceeds the deliberately bounded snapshot size."""


def _safe_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return format(value, "f") if isinstance(value, Decimal) else str(value)
    return value


def request_snapshot(*, user, report_type, filters, idempotency_key, ip_address=None):
    """Create one durable request and enqueue its worker only after the request commits."""
    organization_id = user.organization_id
    if not organization_id:
        raise ValidationError("A user organization is required to request a report.")
    report_queryset(report_type, organization_id, user, filters)
    scope_department_id = None
    if user.role == "DEPARTMENT_MANAGER":
        scope_department_id = user.department_id
    elif filters.get("department"):
        scope_department_id = UUID(str(filters["department"]))

    with transaction.atomic():
        snapshot, created = ReportSnapshot.objects.get_or_create(
            organization_id=organization_id,
            idempotency_key=idempotency_key,
            defaults={
                "requested_by": user,
                "requested_role": user.role,
                "report_type": report_type,
                "parameters": filters,
                "scope_department_id": scope_department_id,
            },
        )
        if not created and (
            snapshot.report_type != report_type
            or snapshot.requested_role != user.role
            or snapshot.parameters != filters
            or snapshot.scope_department_id != scope_department_id
        ):
            raise ValidationError(
                {"idempotency_key": "This key was already used for a different report request."}
            )
        if created:
            record_event(
                organization=user.organization,
                user=user,
                ip_address=ip_address,
                action="REPORT_SNAPSHOT_REQUESTED",
                entity_type="REPORT_SNAPSHOT",
                entity_id=snapshot.pk,
                metadata={
                    "report_type": report_type,
                    "parameters": filters,
                    "scope_department_id": (
                        str(scope_department_id) if scope_department_id else None
                    ),
                },
            )
            transaction.on_commit(lambda: _enqueue_snapshot(snapshot.pk))
        elif snapshot.status == SnapshotStatus.QUEUED:
            # A previous on-commit broker send may have failed after persistence.
            # Re-enqueueing the stable snapshot ID is safe under at-least-once delivery.
            transaction.on_commit(lambda: _enqueue_snapshot(snapshot.pk))
    return snapshot, created


def _enqueue_snapshot(snapshot_id):
    from reporting.tasks import generate_report_snapshot

    generate_report_snapshot.delay(str(snapshot_id))


def _report_user(snapshot):
    """Use the request-time role and scope, even if the requester changes later."""
    from types import SimpleNamespace

    return SimpleNamespace(
        role=snapshot.requested_role,
        department_id=snapshot.scope_department_id,
        is_superuser=False,
    )


def execute_snapshot(*, snapshot_id):
    """Materialize a repeatable-read capture; duplicate deliveries return or resume it."""
    with transaction.atomic():
        snapshot = (
            ReportSnapshot.objects.select_for_update()
            .select_related("organization", "requested_by")
            .get(pk=snapshot_id)
        )
        if snapshot.status in (SnapshotStatus.COMPLETED, SnapshotStatus.FAILED):
            return snapshot
        if snapshot.status == SnapshotStatus.QUEUED:
            snapshot.status = SnapshotStatus.RUNNING
            snapshot.started_at = timezone.now()
            snapshot.save(update_fields=("status", "started_at"))
            record_event(
                organization=snapshot.organization,
                user=None,
                action="REPORT_SNAPSHOT_STARTED",
                entity_type="REPORT_SNAPSHOT",
                entity_id=snapshot.pk,
                changes={"status": {"from": SnapshotStatus.QUEUED, "to": SnapshotStatus.RUNNING}},
                metadata={"report_type": snapshot.report_type},
            )

    with transaction.atomic():
        captured_at = timezone.now()
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                cursor.execute("SELECT transaction_timestamp()")
                captured_at = cursor.fetchone()[0]
        snapshot = (
            ReportSnapshot.objects.select_for_update()
            .select_related("organization", "requested_by")
            .get(pk=snapshot_id)
        )
        if snapshot.status == SnapshotStatus.COMPLETED:
            return snapshot
        if snapshot.status == SnapshotStatus.FAILED:
            return snapshot

        queryset = report_queryset(
            snapshot.report_type,
            snapshot.organization_id,
            _report_user(snapshot),
            snapshot.parameters,
            scope_department_id=snapshot.scope_department_id,
        )
        count = queryset.count()
        if count > MAX_SNAPSHOT_ROWS:
            raise SnapshotTooLarge(
                f"This report has {count} rows, above the {MAX_SNAPSHOT_ROWS} row limit. "
                "Add a date or department filter and request a new snapshot."
            )

        pending = []
        for ordinal, raw_row in enumerate(
            report_rows(queryset, snapshot.report_type).iterator(chunk_size=SNAPSHOT_BATCH_SIZE),
            start=1,
        ):
            row = serialize_report_row(raw_row, snapshot.report_type)
            values = {key: _safe_value(value) for key, value in row.items()}
            pending.append(
                ReportSnapshotRow(
                    snapshot=snapshot,
                    ordinal=ordinal,
                    source_id=str(values["id"]),
                    payload=values,
                )
            )
            if len(pending) == SNAPSHOT_BATCH_SIZE:
                ReportSnapshotRow.objects.bulk_create(pending, batch_size=SNAPSHOT_BATCH_SIZE)
                pending.clear()
        if pending:
            ReportSnapshotRow.objects.bulk_create(pending, batch_size=SNAPSHOT_BATCH_SIZE)

        summary = report_summary(queryset, snapshot.report_type)
        summary["row_count"] = count
        snapshot.status = SnapshotStatus.COMPLETED
        snapshot.as_of = captured_at
        snapshot.generated_at = timezone.now()
        snapshot.row_count = count
        snapshot.summary = summary
        snapshot.failure_class = ""
        snapshot.failure_message = ""
        snapshot.failed_at = None
        snapshot.schema_version = 1
        snapshot.save(
            update_fields=(
                "status",
                "as_of",
                "generated_at",
                "row_count",
                "summary",
                "failure_class",
                "failure_message",
                "failed_at",
                "schema_version",
            )
        )
        record_event(
            organization=snapshot.organization,
            user=None,
            action="REPORT_SNAPSHOT_COMPLETED",
            entity_type="REPORT_SNAPSHOT",
            entity_id=snapshot.pk,
            metadata={
                "report_type": snapshot.report_type,
                "row_count": count,
                "as_of": captured_at.isoformat(),
                "schema_version": snapshot.schema_version,
            },
        )
    return snapshot


def fail_snapshot(*, snapshot_id, failure_class, message):
    with transaction.atomic():
        snapshot = (
            ReportSnapshot.objects.select_for_update()
            .select_related("organization")
            .get(pk=snapshot_id)
        )
        if snapshot.status == SnapshotStatus.COMPLETED:
            return snapshot
        snapshot.status = SnapshotStatus.FAILED
        snapshot.failure_class = str(failure_class)[:100] or "ReportGenerationError"
        snapshot.failure_message = str(message)[:500]
        snapshot.failed_at = timezone.now()
        snapshot.save(update_fields=("status", "failure_class", "failure_message", "failed_at"))
        record_event(
            organization=snapshot.organization,
            user=None,
            action="REPORT_SNAPSHOT_FAILED",
            entity_type="REPORT_SNAPSHOT",
            entity_id=snapshot.pk,
            metadata={
                "report_type": snapshot.report_type,
                "failure_class": snapshot.failure_class,
            },
        )
    return snapshot
