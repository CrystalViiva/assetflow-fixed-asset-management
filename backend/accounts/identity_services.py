"""Transactional identity workflows shared by operator and tenant interfaces."""

from datetime import timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import (
    IdentityDelivery,
    IdentityTicket,
    ManagedProvision,
    PlatformEvent,
    User,
    UserRole,
)
from audit.services import record_event
from organizations.models import Department, Organization

GENERIC_RESPONSE = {"detail": "If this address is eligible, an email will arrive shortly."}


def audit(organization, actor, action, target, metadata=None):
    if organization is None:
        PlatformEvent.objects.create(actor=actor, action=action, target=str(target))
        return
    record_event(
        organization=organization,
        user=actor,
        action=action,
        entity_type="IDENTITY",
        entity_id=target,
        metadata=metadata,
    )


def require_operator(actor):
    if not actor.is_active or not actor.is_platform_operator or actor.organization_id:
        raise PermissionDenied("A platform operator without tenant membership is required.")


def issue_ticket(
    *,
    purpose,
    email,
    organization=None,
    user=None,
    role=UserRole.EMPLOYEE,
    department=None,
    activates=False,
):
    IdentityTicket.objects.filter(
        email=email,
        purpose=purpose,
        organization=organization,
        consumed_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())
    ticket = IdentityTicket.objects.create(
        purpose=purpose,
        email=email,
        organization=organization,
        user=user,
        role=role,
        department=department,
        activates_organization=activates,
        password_fingerprint=user.get_session_auth_hash() if user else "",
        expires_at=timezone.now() + timedelta(hours=1 if purpose == "RESET" else 48),
    )
    IdentityDelivery.objects.create(ticket=ticket, next_attempt_at=timezone.now())
    return ticket


def ticket_token(ticket):
    return signing.dumps(
        {"id": str(ticket.pk), "purpose": ticket.purpose}, salt="assetflow.identity.v1"
    )


def decode_ticket(token, purpose):
    try:
        value = signing.loads(token, salt="assetflow.identity.v1", max_age=48 * 3600)
        if value["purpose"] != purpose:
            raise ValueError
        return IdentityTicket.objects.get(pk=value["id"], purpose=purpose)
    except signing.BadSignature, KeyError, ValueError, TypeError, IdentityTicket.DoesNotExist:
        raise ValidationError("This link is invalid or expired. Request a new email.") from None


def password_check(password, user):
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError({"password": list(exc.messages)}) from None


@transaction.atomic
def accept_ticket(*, token, purpose, password):
    candidate = decode_ticket(token, purpose)
    organization = (
        Organization.objects.select_for_update().get(pk=candidate.organization_id)
        if candidate.organization_id
        else None
    )
    reset_user = (
        User.objects.select_for_update().get(pk=candidate.user_id) if purpose == "RESET" else None
    )
    ticket = IdentityTicket.objects.select_for_update().get(pk=candidate.pk)
    if ticket.consumed_at or ticket.revoked_at or ticket.expires_at <= timezone.now():
        raise ValidationError("This link is invalid or expired. Request a new email.")
    if organization and not organization.is_active and not ticket.activates_organization:
        raise ValidationError("This organization is unavailable.")
    if purpose == "RESET":
        user = reset_user
        if (
            not user.is_active
            or user.email != ticket.email
            or user.get_session_auth_hash() != ticket.password_fingerprint
        ):
            raise ValidationError("This link is invalid or expired. Request a new email.")
    else:
        from commercial.entitlements import require_capacity

        if not ticket.activates_organization:
            require_capacity(organization, "active_users")
        if User.objects.filter(email__iexact=ticket.email).exists():
            raise ValidationError("This invitation cannot be accepted. Contact your administrator.")
        if (
            ticket.department_id
            and not Department.objects.filter(
                pk=ticket.department_id, organization=organization, is_active=True
            ).exists()
        ):
            raise ValidationError(
                "The invited department is unavailable. Request a new invitation."
            )
        user = User(
            email=ticket.email,
            organization=organization,
            role=ticket.role,
            department=ticket.department,
        )
    password_check(password, user)
    user.set_password(password)
    user.session_version += 1
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError:
        raise ValidationError(
            "This invitation cannot be accepted. Contact your administrator."
        ) from None
    ticket.consumed_at = timezone.now()
    ticket.user = user
    ticket.save(update_fields=["consumed_at", "user"])
    if ticket.activates_organization:
        from commercial.models import Plan, Subscription

        managed_plan, _ = Plan.objects.get_or_create(
            code="managed",
            version=1,
            defaults={
                "name": "Managed service",
                "monthly_amount": 0,
                "trial_days": 0,
                "active_users": None,
                "registered_assets": None,
                "is_public": False,
                "is_sandbox": False,
            },
        )
        Subscription.objects.get_or_create(
            organization=organization,
            defaults={
                "owner": user,
                "plan": managed_plan,
                "state": "MANAGED",
                "billing_email": user.email,
                "provider": "disabled",
            },
        )
        organization.is_active = True
        organization.save(update_fields=["is_active", "updated_at"])
    audit(
        organization,
        user,
        "PASSWORD_RESET" if purpose == "RESET" else "INVITATION_ACCEPTED",
        ticket.pk,
    )
    return user


@transaction.atomic
def invite(*, actor, email, role, department_id=None):
    if (
        actor.role != UserRole.ADMIN
        or not actor.organization_id
        or actor.is_platform_operator
        or actor.is_superuser
        or not actor.is_active
    ):
        raise PermissionDenied("Organization administrator required.")
    organization = Organization.objects.select_for_update().get(
        pk=actor.organization_id, is_active=True
    )
    if role not in UserRole.values:
        raise ValidationError({"role": "Select an organization role."})
    department = None
    if department_id:
        department = Department.objects.filter(
            pk=department_id, organization=organization, is_active=True
        ).first()
        if not department:
            raise ValidationError(
                {"department_id": "Choose an active department in this organization."}
            )
    if User.objects.filter(email__iexact=email).exists():
        return None
    ticket = issue_ticket(
        purpose="INVITE", email=email, organization=organization, role=role, department=department
    )
    audit(organization, actor, "INVITATION_CREATED", ticket.pk)
    return ticket


@transaction.atomic
def provision(*, actor, key, name, code, email, currency="NGN", timezone_name="Africa/Lagos"):
    require_operator(actor)
    User.objects.select_for_update().get(pk=actor.pk)
    params = dict(
        name=name.strip(),
        code=code.strip().upper(),
        email=email.strip().lower(),
        currency=currency,
        timezone=timezone_name,
    )
    previous = ManagedProvision.objects.filter(pk=key).first()
    if previous:
        if previous.parameters != params:
            raise ValidationError("The idempotency key was already used for different details.")
        return previous
    if (
        not params["name"]
        or not params["code"]
        or currency not in {"NGN", "USD", "GBP", "EUR", "GHS", "KES", "ZAR"}
    ):
        raise ValidationError("Provide a company name, unique code and supported currency.")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError, ValueError:
        raise ValidationError({"timezone": "Select an IANA timezone."}) from None
    if User.objects.filter(email__iexact=params["email"]).exists():
        raise ValidationError("This administrator address is unavailable.")
    try:
        with transaction.atomic():
            organization = Organization.objects.create(
                name=params["name"],
                code=params["code"],
                currency=currency,
                timezone=timezone_name,
                is_active=False,
            )
            ticket = issue_ticket(
                purpose="INVITE",
                email=params["email"],
                organization=organization,
                role=UserRole.ADMIN,
                activates=True,
            )
            result = ManagedProvision.objects.create(
                key=key,
                organization=organization,
                invitation=ticket,
                requested_by=actor,
                parameters=params,
            )
    except IntegrityError:
        previous = ManagedProvision.objects.filter(pk=key).first()
        if previous and previous.parameters == params:
            return previous
        raise ValidationError("The company code or request key is already in use.") from None
    audit(organization, actor, "ORGANIZATION_PROVISIONED", organization.pk)
    return result


def deliver_pending(limit=100):
    """SMTP is at-least-once. Duplicate email after a crash cannot duplicate activation."""
    sent = 0
    for _ in range(limit):
        with transaction.atomic():
            delivery = (
                IdentityDelivery.objects.select_for_update(skip_locked=True)
                .filter(sent_at__isnull=True, next_attempt_at__lte=timezone.now(), attempts__lt=8)
                .order_by("pk")
                .first()
            )
            if not delivery:
                break
            ticket = delivery.ticket
            if ticket.consumed_at or ticket.revoked_at or ticket.expires_at <= timezone.now():
                delivery.last_error, delivery.attempts = "ticket_closed", 8
                delivery.save(update_fields=["last_error", "attempts"])
                continue
            base = settings.FRONTEND_BASE_URL.rstrip("/")
            parsed = urlsplit(base)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.fragment
                or parsed.query
            ):
                raise ValueError("FRONTEND_BASE_URL must be a trusted HTTP(S) origin.")
            route = {
                "INVITE": "accept-invitation",
                "RESET": "reset-password",
                "VERIFY": "verify-email",
            }[ticket.purpose]
            link = f"{base}/#{route}?token={ticket_token(ticket)}"
            delivery.attempts += 1
            try:
                send_mail(
                    "Your AssetFlow account link",
                    f"Use this one-time link to continue with AssetFlow:\n\n{link}\n\n"
                    f"Expires: {ticket.expires_at.isoformat()}. "
                    "If you did not request this, ignore it.\n"
                    "AssetFlow will never ask you to send your password by email.",
                    settings.DEFAULT_FROM_EMAIL,
                    [ticket.email],
                    fail_silently=False,
                )
                delivery.sent_at, delivery.last_error = timezone.now(), ""
                sent += 1
            except Exception as exc:
                delivery.last_error = type(exc).__name__[:80]
                delivery.next_attempt_at = timezone.now() + timedelta(
                    seconds=min(3600, 30 * 2**delivery.attempts)
                )
            delivery.save()
    return sent
