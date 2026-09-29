"""Celery orchestration and execution tasks for scheduled depreciation."""

from celery import shared_task

from depreciation.services.automation import execute_monthly_run, schedule_monthly_depreciation


@shared_task(acks_late=True, reject_on_worker_lost=True)
def schedule_monthly_depreciation_run():
    """Schedule the current calendar month; workers perform postings separately."""
    return schedule_monthly_depreciation()


@shared_task(acks_late=True, reject_on_worker_lost=True)
def execute_monthly_depreciation_run(run_id):
    """Execute a durable monthly run through the existing posting service."""
    return execute_monthly_run(run_id=run_id)
