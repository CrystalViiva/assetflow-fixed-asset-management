from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import APIException

from accounts.identity_api import ProvisionInput
from accounts.identity_services import provision
from accounts.models import User


class Command(BaseCommand):
    help = "Idempotently provision a pending company and queue its administrator invitation."

    def add_arguments(self, parser):
        for name in ("operator", "key", "name", "code", "email"):
            parser.add_argument(f"--{name}", required=True)
        parser.add_argument("--currency", default="NGN")
        parser.add_argument("--timezone", default="Africa/Lagos")

    def handle(self, *args, **options):
        actor = User.objects.filter(email=options["operator"].strip().lower()).first()
        if actor is None:
            raise CommandError("Operator account not found.")
        data = {key: options[key] for key in ("key", "name", "code", "email", "currency")}
        data["timezone_name"] = options["timezone"]
        serializer = ProvisionInput(data=data)
        try:
            serializer.is_valid(raise_exception=True)
            result = provision(actor=actor, **serializer.validated_data)
        except APIException as exc:
            raise CommandError(str(exc.detail)) from None
        self.stdout.write(
            f"Organization {result.organization_id}; activation queued. No password generated."
        )
