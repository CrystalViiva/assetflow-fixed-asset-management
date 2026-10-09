import os

from celery import Celery
from celery.schedules import crontab

from assurance.constants import (
    DAILY_FULL_SCHEDULE_HOUR,
    DAILY_FULL_SCHEDULE_ID,
    DAILY_FULL_SCHEDULE_MINUTE,
)
from depreciation.constants import (
    MONTHLY_DEPRECIATION_SCHEDULE_DAY,
    MONTHLY_DEPRECIATION_SCHEDULE_HOUR,
    MONTHLY_DEPRECIATION_SCHEDULE_ID,
    MONTHLY_DEPRECIATION_SCHEDULE_MINUTE,
)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("assetflow")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule = {
    "billing-reconciliation": {
        "task": "commercial.tasks.reconcile_billing",
        "schedule": 60.0,
    },
    "operational-heartbeat": {
        "task": "operations.tasks.heartbeat",
        "schedule": 60.0,
    },
    "identity-mail": {
        "task": "accounts.tasks.deliver_identity_mail",
        "schedule": 30.0,
    },
    "recover-unfinished-assurance": {
        "task": "assurance.tasks.recover_assurance_runs",
        "schedule": 60.0,
    },
    "recover-report-exports": {
        "task": "reporting.tasks.recover_report_exports",
        "schedule": 300.0,
    },
    "expire-report-exports": {
        "task": "reporting.tasks.expire_report_exports",
        "schedule": 3600.0,
    },
    "clean-stale-evidence-uploads": {
        "task": "verification.tasks.clean_stale_evidence_uploads",
        "schedule": 900.0,
    },
    DAILY_FULL_SCHEDULE_ID: {
        "task": "assurance.tasks.schedule_daily_assurance",
        "schedule": crontab(
            hour=DAILY_FULL_SCHEDULE_HOUR,
            minute=DAILY_FULL_SCHEDULE_MINUTE,
        ),
    },
    MONTHLY_DEPRECIATION_SCHEDULE_ID: {
        "task": "depreciation.tasks.schedule_monthly_depreciation_run",
        "schedule": crontab(
            day_of_month=MONTHLY_DEPRECIATION_SCHEDULE_DAY,
            hour=MONTHLY_DEPRECIATION_SCHEDULE_HOUR,
            minute=MONTHLY_DEPRECIATION_SCHEDULE_MINUTE,
        ),
    },
}
