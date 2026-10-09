import logging

from celery.signals import task_failure

from operations.models import TaskFailure


@task_failure.connect
def record_failure(sender=None, task_id=None, exception=None, **kwargs):
    try:
        TaskFailure.objects.get_or_create(
            task_id=str(task_id)[:128],
            defaults={
                "task_name": str(getattr(sender, "name", "unknown"))[:240],
                "error_type": type(exception).__name__[:100],
            },
        )
    except Exception:
        logging.getLogger(__name__).error(
            "Worker failure record unavailable; check database health"
        )
