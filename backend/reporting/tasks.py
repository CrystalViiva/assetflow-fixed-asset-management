"""At-least-once Celery orchestration for durable report snapshots."""

from celery import shared_task

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
