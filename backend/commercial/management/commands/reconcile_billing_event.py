from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.identity_services import require_operator
from accounts.models import PlatformEvent, User
from commercial.billing import process_event
from commercial.models import BillingEvent


class Command(BaseCommand):
    help = "Retry an authenticated stored provider event after resolving its operational failure."

    def add_arguments(self, parser):
        parser.add_argument("event_id")
        parser.add_argument("--operator", required=True)

    def handle(self, *args, **options):
        actor = User.objects.filter(email=options["operator"].lower()).first()
        if not actor:
            raise CommandError("Operator not found.")
        require_operator(actor)
        with transaction.atomic():
            event = BillingEvent.objects.select_for_update().filter(pk=options["event_id"]).first()
            if not event:
                raise CommandError("Stored provider event not found.")
            if event.status == "FAILED":
                event.attempts, event.status = 0, "PENDING"
                event.save(update_fields=["attempts", "status"])
            PlatformEvent.objects.create(
                actor=actor, action="BILLING_EVENT_RETRIED", target=event.pk
            )
        result = process_event(event.pk)
        self.stdout.write(f"Reconciliation status: {result.status}")
        if result.status == "FAILED":
            raise CommandError("Provider reconciliation still requires attention.")
