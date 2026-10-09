from celery import shared_task

from commercial.billing import process_event
from commercial.models import BillingEvent


@shared_task(ignore_result=True)
def reconcile_billing():
    for pk in (
        BillingEvent.objects.filter(status__in=["PENDING", "FAILED"], attempts__lt=8)
        .order_by("received_at")
        .values_list("pk", flat=True)[:100]
    ):
        process_event(pk)
