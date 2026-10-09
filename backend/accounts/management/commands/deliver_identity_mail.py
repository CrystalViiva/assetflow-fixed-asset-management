from django.core.management.base import BaseCommand

from accounts.identity_services import deliver_pending


class Command(BaseCommand):
    help = "Deliver pending account links using configured email backend; retry failures safely."

    def handle(self, *args, **options):
        self.stdout.write(f"Delivered {deliver_pending()} message(s).")
