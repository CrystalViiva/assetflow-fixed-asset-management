import os

from celery import Celery
from celery.schedules import crontab

from assurance.constants import (
    DAILY_FULL_SCHEDULE_HOUR,
    DAILY_FULL_SCHEDULE_ID,
    DAILY_FULL_SCHEDULE_MINUTE,
)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("assetflow")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule = {
    DAILY_FULL_SCHEDULE_ID: {
        "task": "assurance.tasks.schedule_daily_assurance",
        "schedule": crontab(
            hour=DAILY_FULL_SCHEDULE_HOUR,
            minute=DAILY_FULL_SCHEDULE_MINUTE,
        ),
    }
}
