"""At-least-once Celery orchestration for durable report snapshots."""

from celery import shared_task

from reporting.exports import (
    ExportAttemptError,
    cleanup_failed_exports,
    execute_export,
    expire_exports,
    fail_export,
    recover_exports,
)
from reporting.services import SnapshotTooLarge, execute_snapshot, fail_snapshot


@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True, max_retries=2)
def generate_report_snapshot(self, snapshot_id):
    try:
        snapshot = execute_snapshot(snapshot_id=snapshot_id)
    except SnapshotTooLarge as exc:
        snapshot = fail_snapshot(
            snapshot_id=snapshot_id,
            failure_class=type(exc).__name__,
            message=str(exc),
        )
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
        fail_snapshot(
            snapshot_id=snapshot_id,
            failure_class=type(exc).__name__,
            message="Snapshot generation failed after retries.",
        )
        raise
    return {
        "snapshot_id": str(snapshot.pk),
        "status": snapshot.status,
        "row_count": snapshot.row_count,
    }


@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True, max_retries=3)
def generate_report_export(self, export_id):
    try:
        export = execute_export(export_id=export_id)
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
        fail_export(
            export_id=export_id,
            exc=exc.cause if isinstance(exc, ExportAttemptError) else exc,
            attempt_token=exc.attempt_token if isinstance(exc, ExportAttemptError) else None,
        )
        raise
    if export is None:
        return {"export_id": str(export_id), "status": "MISSING"}
    return {"export_id": str(export.pk), "status": export.status}


@shared_task
def recover_report_exports():
    recovered = recover_exports()
    cleanup_failed_exports()
    return {"requeued": recovered}


@shared_task
def expire_report_exports():
    return {"expired": expire_exports()}
