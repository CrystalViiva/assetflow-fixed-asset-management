"""Celery tasks for durable assurance runs."""

from celery import shared_task
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from assurance.models import AssuranceRun
from assurance.services.execution import advance_run, recover_unfinished_runs
from assurance.services.scheduling import schedule_daily_full_assurance


@shared_task(acks_late=True, reject_on_worker_lost=True)
def execute_assurance_run(run_id):
    """Evaluate a persisted assurance run using its recorded organization and actor."""
    run = AssuranceRun.objects.select_related("organization", "started_by").get(pk=run_id)
    if run.started_by_id and run.started_by.organization_id != run.organization_id:
        raise ValidationError({"run": "The stored actor is outside the run organization."})

    completed = advance_run(run_id=run.pk, actor=run.started_by, organization=run.organization)
    if completed.status == "RUNNING":
        delay = (
            max(0, (completed.next_attempt_at - timezone.now()).total_seconds())
            if (completed.next_attempt_at)
            else 0
        )
        transaction.on_commit(
            lambda: execute_assurance_run.apply_async(args=(str(completed.pk),), countdown=delay),
            robust=True,
        )
    return {
        "run_id": str(completed.pk),
        "status": str(completed.status),
        "assets_evaluated": completed.assets_evaluated,
        "findings_generated": completed.findings_generated,
    }


@shared_task(acks_late=True, reject_on_worker_lost=True)
def schedule_daily_assurance():
    """Create and dispatch daily runs; the assurance execution task evaluates them."""
    return schedule_daily_full_assurance()


@shared_task(acks_late=True, reject_on_worker_lost=True)
def recover_assurance_runs():
    return {"runs_dispatched": recover_unfinished_runs()}
