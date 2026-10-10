from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.identity_services import require_operator
from accounts.models import PlatformEvent, User
from commercial.models import Plan, ProviderPlan
from commercial.providers import provider


class Command(BaseCommand):
    help = "Map an immutable local plan to an existing, verified Paystack test monthly plan."

    def add_arguments(self, parser):
        parser.add_argument("plan_id")
        parser.add_argument("provider_code")
        parser.add_argument("--operator", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        actor = User.objects.filter(email=options["operator"].lower()).first()
        if not actor:
            raise CommandError("Operator not found.")
        require_operator(actor)
        plan = Plan.objects.select_for_update().get(pk=options["plan_id"], is_sandbox=True)
        adapter = provider("paystack_test")
        adapter.check_plan(plan, options["provider_code"])
        mapping, _ = ProviderPlan.objects.get_or_create(
            plan=plan, defaults={"code": options["provider_code"]}
        )
        if mapping.code != options["provider_code"]:
            raise CommandError(
                "Publish a new plan version instead of replacing a provider mapping."
            )
        PlatformEvent.objects.create(
            actor=actor, action="PAYSTACK_PLAN_MAPPED", target=str(plan.pk)
        )
        self.stdout.write("Verified test plan mapping saved. No charge was created.")
