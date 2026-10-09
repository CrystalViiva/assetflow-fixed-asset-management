from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from accounts.models import RateBucket
from operations.models import TaskFailure, WorkerPulse


@shared_task(ignore_result=True)
def heartbeat():
    WorkerPulse.objects.update_or_create(name="default", defaults={"seen_at": timezone.now()})
    RateBucket.objects.filter(started_at__lt=timezone.now() - timedelta(days=1)).delete()
    TaskFailure.objects.filter(occurred_at__lt=timezone.now() - timedelta(days=90)).delete()
