"""Idempotent subscription transitions from authenticated provider evidence."""

import hashlib
import json
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.identity_services import audit
from commercial.entitlements import usage
from commercial.models import BillingEvent, Checkout, Plan, Subscription
from commercial.providers import provider
from organizations.models import Organization


def tenant_admin(actor):
    if (
        not actor.is_active
        or actor.role != "ADMIN"
        or not actor.organization_id
        or actor.is_platform_operator
        or actor.is_superuser
    ):
        raise PermissionDenied("Organization administrator required.")


def fits(plan, organization):
    current = usage(organization)
    for dimension, count in current.items():
        limit = getattr(plan, dimension)
        if limit is not None and count > limit:
            raise ValidationError(
                f"Current {dimension.replace('_', ' ')} exceed this plan. No records were removed."
            )


@transaction.atomic
def _allocate_checkout(*, actor, plan_id, request_key):
    tenant_admin(actor)
    Organization.objects.select_for_update().get(pk=actor.organization_id)
    subscription = (
        Subscription.objects.select_for_update().filter(organization=actor.organization).first()
    )
    if not subscription:
        raise ValidationError(
            "This company uses managed commercial terms. Contact your account operator."
        )
    if subscription.state == "SUSPENDED":
        raise PermissionDenied("This subscription requires operator review before new checkout.")
    previous = Checkout.objects.filter(
        organization=actor.organization, request_key=request_key
    ).first()
    if previous:
        if str(previous.plan_id) != str(plan_id):
            raise ValidationError("This request key was already used for another plan.")
        return previous
    plan = Plan.objects.filter(pk=plan_id, is_public=True, is_sandbox=True).first()
    if not plan:
        raise ValidationError("Select an available sandbox plan.")
    fits(plan, actor.organization)
    adapter = provider()
    checkout = Checkout.objects.create(
        organization=actor.organization,
        plan=plan,
        request_key=request_key,
        amount_minor=int(plan.monthly_amount * 100),
        currency=plan.currency,
        provider=adapter.name,
        provider_reference=f"af_{uuid4().hex}",
    )
    audit(actor.organization, actor, "SANDBOX_CHECKOUT_CREATED", checkout.pk)
    return checkout


def initialize_checkout(*, actor, plan_id, request_key):
    checkout = _allocate_checkout(actor=actor, plan_id=plan_id, request_key=request_key)
    if checkout.provider_url:
        return checkout
    # Preserve the reference even if the provider replies ambiguously or the network fails.
    with transaction.atomic():
        checkout = Checkout.objects.select_for_update().get(pk=checkout.pk)
        if not checkout.provider_url:
            subscription = Subscription.objects.get(organization=checkout.organization)
            try:
                checkout.provider_url = provider(checkout.provider).initialize(
                    checkout, subscription.billing_email
                )
            except Exception:
                raise ValidationError(
                    "Sandbox checkout could not be confirmed. "
                    "Retry this request or ask your operator to reconcile its reference."
                ) from None
            checkout.save(update_fields=["provider_url"])
    return checkout


def receive_webhook(*, body, signature):
    adapter = provider()
    if len(body) > 64_000 or not adapter.verify_signature(body, signature):
        raise PermissionDenied("Invalid webhook signature.")
    try:
        payload = json.loads(body)
        event_type = payload["event"]
        reference = payload["data"]["reference"]
        if (
            not isinstance(event_type, str)
            or len(event_type) > 80
            or not isinstance(reference, str)
            or len(reference) > 120
        ):
            raise ValueError
    except ValueError, KeyError, TypeError:
        raise ValidationError("Invalid webhook payload.") from None
    # Persist only allowlisted metadata, never card/customer payloads.
    event, _ = BillingEvent.objects.get_or_create(
        id=hashlib.sha256(body).hexdigest(),
        defaults={"provider": adapter.name, "reference": reference, "event_type": event_type},
    )
    return event


@transaction.atomic
def process_event(event_id):
    event = BillingEvent.objects.select_for_update().get(pk=event_id)
    if event.status in {"PROCESSED", "IGNORED"}:
        return event
    checkout = Checkout.objects.filter(
        provider_reference=event.reference, provider=event.provider
    ).first()
    if not checkout:
        event.status, event.last_error = "IGNORED", "unknown_reference"
        event.save(update_fields=["status", "last_error"])
        return event
    Organization.objects.select_for_update().get(pk=checkout.organization_id)
    checkout = Checkout.objects.select_for_update().get(pk=checkout.pk)
    subscription = Subscription.objects.select_for_update().get(organization=checkout.organization)
    event.attempts += 1
    try:
        with transaction.atomic():
            verified = provider(event.provider).verify(event.reference)
            if (
                verified["reference"] != checkout.provider_reference
                or verified["amount_minor"] != checkout.amount_minor
                or verified["currency"] != checkout.currency
            ):
                raise ValidationError("Provider transaction does not match the checkout.")
            event_at = verified["occurred_at"]
            if event_at is None:
                raise ValidationError("Provider transaction has not completed.")
            if event_at > timezone.now() + timedelta(minutes=5):
                raise ValidationError("Provider timestamp is invalid.")
            status = verified["status"]
            terminal = checkout.status in {"REFUNDED", "CHARGEBACK"}
            if terminal or (subscription.last_event_at and event_at < subscription.last_event_at):
                event.status = "IGNORED"
            elif subscription.canceled_at and checkout.created_at <= subscription.canceled_at:
                event.status = "IGNORED"
            elif status == "SUCCEEDED" and checkout.status != "SUCCEEDED":
                fits(checkout.plan, checkout.organization)
                checkout.status, checkout.settled_at = status, event_at
                same_plan = subscription.plan_id == checkout.plan_id
                start = (
                    max(subscription.period_ends_at, event_at)
                    if same_plan and subscription.period_ends_at
                    else event_at
                )
                subscription.plan, subscription.state = checkout.plan, "ACTIVE"
                subscription.entitlement_checkout = checkout
                subscription.period_ends_at = start + timedelta(days=30)
                subscription.grace_ends_at = None
                subscription.cancel_at_period_end, subscription.canceled_at = False, None
                subscription.provider = event.provider
                subscription.provider_customer = verified["customer"]
                subscription.provider_subscription = (
                    f"sandbox-{subscription.organization_id}"
                    if event.provider == "local_sandbox"
                    else ""
                )
                subscription.last_event_at = event_at
                event.status = "PROCESSED"
            elif status in {"REFUNDED", "CHARGEBACK"}:
                checkout.status = status
                if subscription.entitlement_checkout_id == checkout.pk:
                    subscription.state = "SUSPENDED"
                    subscription.last_event_at = event_at
                event.status = "PROCESSED"
            elif status == "FAILED" and checkout.status != "SUCCEEDED":
                checkout.status = "FAILED"
                # Failed renewal grants at most seven days from the already-earned paid period.
                if subscription.state in {"ACTIVE", "PAST_DUE"} and subscription.period_ends_at:
                    subscription.state = "PAST_DUE"
                    subscription.grace_ends_at = subscription.period_ends_at + timedelta(days=7)
                subscription.last_event_at = event_at
                event.status = "PROCESSED"
            else:
                event.status = "IGNORED"
            checkout.save()
            subscription.save()
            event.last_error, event.processed_at = "", timezone.now()
            audit(checkout.organization, None, f"BILLING_EVENT_{event.status}", event.pk)
    except Exception as exc:
        event.status, event.last_error = "FAILED", type(exc).__name__[:100]
    event.save()
    return event


@transaction.atomic
def simulate(*, actor, checkout_id, outcome):
    tenant_admin(actor)
    if settings.ASSETFLOW_ENV == "production" or settings.BILLING_PROVIDER != "local_sandbox":
        raise PermissionDenied("Local sandbox simulation is unavailable.")
    Organization.objects.select_for_update().get(pk=actor.organization_id)
    checkout = (
        Checkout.objects.select_for_update()
        .filter(pk=checkout_id, organization=actor.organization, provider="local_sandbox")
        .first()
    )
    if not checkout:
        raise ValidationError("Checkout not found in this organization.")
    if outcome not in {"SUCCEEDED", "FAILED", "REFUNDED", "CHARGEBACK"}:
        raise ValidationError("Unsupported sandbox outcome.")
    checkout.sandbox_status, checkout.sandbox_updated_at = outcome, timezone.now()
    checkout.sandbox_sequence += 1
    checkout.save(update_fields=["sandbox_status", "sandbox_updated_at", "sandbox_sequence"])
    body = json.dumps(
        {
            "event": f"sandbox.{outcome.lower()}",
            "data": {
                "reference": checkout.provider_reference,
                "sequence": checkout.sandbox_sequence,
            },
        },
        sort_keys=True,
    ).encode()
    event = receive_webhook(body=body, signature=provider().signature(body))
    # Caller processes after releasing organization lock (consistent event -> org lock order).
    return event


@transaction.atomic
def cancel(*, actor):
    tenant_admin(actor)
    Organization.objects.select_for_update().get(pk=actor.organization_id)
    subscription = (
        Subscription.objects.select_for_update().filter(organization=actor.organization).first()
    )
    if not subscription:
        raise ValidationError("Contact your operator to cancel managed service.")
    subscription.cancel_at_period_end = True
    subscription.canceled_at = timezone.now()
    if subscription.state == "TRIAL":
        subscription.state = "CANCELED"
    subscription.save()
    audit(actor.organization, actor, "SUBSCRIPTION_CANCELLATION_REQUESTED", subscription.pk)
    return subscription
