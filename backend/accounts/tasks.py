from celery import shared_task

from accounts.identity_services import deliver_pending


@shared_task(ignore_result=True)
def deliver_identity_mail():
    return deliver_pending()
