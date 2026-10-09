from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.identity_services import audit, decode_ticket, issue_ticket, password_check
from accounts.models import IdentityTicket, User
from commercial.models import Plan, Registration, Subscription
from organizations.models import Organization


@transaction.atomic
def request_signup(*, email, company_name, currency, timezone_name):
    if not settings.SELF_SERVICE_ENABLED:
        raise PermissionDenied(
            "Self-service registration is not enabled. Contact sales for managed onboarding."
        )
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError, ValueError:
        raise ValidationError({"timezone_name": "Select an IANA timezone."}) from None
    if currency not in {"NGN", "USD", "GBP", "EUR", "GHS", "KES", "ZAR"}:
        raise ValidationError({"currency": "Select a supported currency."})
    if User.objects.filter(email=email).exists():
        return
    existing = Registration.objects.select_for_update().filter(email=email).first()
    if existing:
        if existing.organization_id:
            return
        existing.ticket = issue_ticket(purpose="VERIFY", email=email)
        # Resend never silently changes the company already awaiting verification.
        existing.save(update_fields=["ticket"])
        return
    try:
        with transaction.atomic():
            ticket = issue_ticket(purpose="VERIFY", email=email)
            Registration.objects.create(
                email=email,
                company_name=company_name,
                currency=currency,
                timezone=timezone_name,
                ticket=ticket,
            )
    except IntegrityError:
        # Concurrent identical registration: one pending record and mail delivery wins.
        return


@transaction.atomic
def verify_signup(*, token, password, plan_id):
    if not settings.SELF_SERVICE_ENABLED:
        raise PermissionDenied("Self-service registration is not enabled.")
    candidate = decode_ticket(token, "VERIFY")
    registration = Registration.objects.select_for_update().filter(ticket=candidate).first()
    if not registration:
        raise ValidationError("This verification link has been replaced. Use the latest email.")
    ticket = IdentityTicket.objects.select_for_update().get(pk=candidate.pk)
    if (
        registration.organization_id
        or ticket.consumed_at
        or ticket.revoked_at
        or ticket.expires_at <= timezone.now()
    ):
        raise ValidationError("This verification link is expired or already used.")
    plan = Plan.objects.filter(pk=plan_id, is_public=True, trial_days__gt=0).first()
    if not plan:
        raise ValidationError({"plan_id": "Select an available trial plan."})
    user = User(email=registration.email, role="ADMIN", session_version=1)
    password_check(password, user)
    try:
        with transaction.atomic():
            org = Organization.objects.create(
                name=registration.company_name,
                code=f"CO-{uuid4().hex[:24].upper()}",
                currency=registration.currency,
                timezone=registration.timezone,
            )
            user.organization = org
            user.set_password(password)
            user.save()
            Subscription.objects.create(
                organization=org,
                owner=user,
                plan=plan,
                state="TRIAL",
                trial_ends_at=timezone.now() + timedelta(days=plan.trial_days),
                billing_email=user.email,
            )
    except IntegrityError:
        raise ValidationError(
            "This address already has an account. Sign in or recover your password."
        ) from None
    ticket.consumed_at = timezone.now()
    ticket.save(update_fields=["consumed_at"])
    registration.organization = org
    registration.save(update_fields=["organization"])
    audit(org, user, "SELF_SERVICE_ORGANIZATION_VERIFIED", org.pk)
    return org
