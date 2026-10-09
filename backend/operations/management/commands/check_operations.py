import json

from django.core.management.base import BaseCommand, CommandError

from operations.api import operational_health


class Command(BaseCommand):
    help = "Emit non-sensitive monitoring JSON; exit nonzero when operator action is needed."

    def handle(self, *args, **options):
        values = operational_health()
        self.stdout.write(json.dumps(values))
        if (
            not values["worker_recent"]
            or not values["private_storage"]
            or values["mail_failed"]
            or values["task_failures_24h"]
        ):
            raise CommandError("Operational health requires attention.")
