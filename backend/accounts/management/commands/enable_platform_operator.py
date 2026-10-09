from django.core.management.base import BaseCommand, CommandError

from accounts.models import PlatformEvent, User


class Command(BaseCommand):
    help = "Enable operator capability for an unscoped superuser; local operator access required."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, *args, **options):
        user = User.objects.filter(
            email=options["email"].strip().lower(),
            is_superuser=True,
            is_active=True,
            organization__isnull=True,
        ).first()
        if not user:
            raise CommandError("An active superuser without organization membership is required.")
        user.is_platform_operator = True
        user.save(update_fields=["is_platform_operator"])
        PlatformEvent.objects.create(
            actor=user, action="OPERATOR_ENABLED_LOCALLY", target=str(user.pk)
        )
        self.stdout.write("Platform operator capability enabled.")
