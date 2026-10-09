import hashlib

from django.core.management.base import BaseCommand, CommandError

from accounts.identity_services import require_operator
from accounts.models import PlatformEvent, User
from commercial.billing import process_event
from commercial.models import BillingEvent, Checkout


class Command(BaseCommand):
    help = (
        "Reconcile one stored sandbox checkout against the provider; never trust a browser result."
    )

    def add_arguments(self, parser):
        parser.add_argument("reference")
        parser.add_argument("--operator", required=True)

    def handle(self, *args, **options):
        actor = User.objects.filter(email=options["operator"].lower()).first()
        if not actor:
            raise CommandError("Operator not found.")
        require_operator(actor)
        checkout = Checkout.objects.filter(provider_reference=options["reference"]).first()
        if not checkout:
            raise CommandError("Stored checkout not found.")
        digest = hashlib.sha256(f"reconcile:{checkout.provider}:{checkout.pk}".encode()).hexdigest()
        event, _ = BillingEvent.objects.get_or_create(
            id=digest,
            defaults={
                "provider": checkout.provider,
                "reference": checkout.provider_reference,
                "event_type": "operator.reconciliation",
            },
        )
        if event.status == "FAILED":
            event.attempts = 0
            event.save(update_fields=["attempts"])
        result = process_event(event.pk)
        PlatformEvent.objects.create(
            actor=actor, action="BILLING_RECONCILED", target=str(checkout.pk)
        )
        self.stdout.write(f"Reconciliation status: {result.status}")
        if result.status == "FAILED":
            raise CommandError(
                "Provider confirmation is unavailable; inspect operational metadata."
            )
