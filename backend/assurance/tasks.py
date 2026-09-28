"""Celery tasks for durable assurance runs."""

from celery import shared_task
from django.core.exceptions import ValidationError

from assurance.models import AssuranceRun
from assurance.services.runs import execute_run


@shared_task(acks_late=True, reject_on_worker_lost=True)
def execute_assurance_run(run_id):
    """Evaluate a persisted assurance run using its recorded organization and actor."""
    run = AssuranceRun.objects.select_related("organization", "started_by").get(pk=run_id)
    if run.started_by.organization_id != run.organization_id:
        raise ValidationError({"run": "The stored actor is outside the run organization."})

    completed = execute_run(run_id=run.pk, actor=run.started_by)
    return {
        "run_id": str(completed.pk),
        "status": str(completed.status),
        "assets_evaluated": completed.assets_evaluated,
        "findings_generated": completed.findings_generated,
    }
