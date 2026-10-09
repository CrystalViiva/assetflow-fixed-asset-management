from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.identity_services import require_operator
from accounts.models import PlatformEvent, User
from commercial.models import SalesLead


class Command(BaseCommand):
    help = "Review expired CLOSED enquiries; explicit confirmation anonymizes contact data."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--operator", required=True)
        parser.add_argument("--anonymize", action="store_true")
        parser.add_argument("--confirm", default="")

    def handle(self, *args, **options):
        actor = User.objects.filter(email=options["operator"].lower()).first()
        if not actor:
            raise CommandError("Operator not found.")
        require_operator(actor)
        if options["days"] < 90:
            raise CommandError("Minimum retention review window is 90 days.")
        rows = SalesLead.objects.filter(
            status="CLOSED", updated_at__lt=timezone.now() - timedelta(days=options["days"])
        ).exclude(email="removed@example.invalid")
        self.stdout.write(f"Eligible closed enquiries: {rows.count()}")
        if options["anonymize"]:
            if options["confirm"] != "ANONYMIZE_CLOSED_ENQUIRIES":
                raise CommandError(
                    "Use --confirm ANONYMIZE_CLOSED_ENQUIRIES after reviewing legal holds."
                )
            count = rows.update(
                name="Removed",
                email="removed@example.invalid",
                company="Removed",
                phone="",
                requirements="Removed after retention review",
            )
            PlatformEvent.objects.create(
                actor=actor, action="CLOSED_LEADS_ANONYMIZED", target=str(count)
            )
            self.stdout.write(f"Anonymized {count} closed enquiries.")
