"""Paystack test subscriptions. Signed notifications are reconciled with provider records.

Only identifiers and invoice terms survive webhook ingestion. Authorization/card data and
subscription email tokens must never be stored, logged or sent to the browser.
"""

from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from accounts.identity_services import audit
from commercial.models import (
    Checkout,
    ProviderCustomer,
    ProviderPlan,
    ProviderSubscription,
    Subscription,
)
from commercial.providers import PaystackTestProvider
from organizations.models import Organization

SUBSCRIPTION_EVENTS = {"subscription.create", "subscription.not_renew", "subscription.disable"}
INVOICE_EVENTS = {"invoice.update", "invoice.payment_failed"}
REVERSAL_EVENTS = {
    "refund.processed",
    "charge.dispute.create",
    "charge.dispute.remind",
    "charge.dispute.resolve",
}


def event_metadata(payload):
    event, data = payload.get("event"), payload.get("data")
    if not isinstance(event, str) or not isinstance(data, dict):
        raise ValueError
    if event in REVERSAL_EVENTS:
        identifier = data.get("id")
        if type(identifier) is not int or identifier < 1:
            raise ValueError
        return str(identifier), {"object_id": identifier}
    if event not in SUBSCRIPTION_EVENTS | INVOICE_EVENTS | {"charge.success"}:
        return "", {}  # Acknowledge unrelated merchant events without storing their payloads.
    if data.get("domain") != "test":
        raise ValueError
    if event == "charge.success":
        return data.get("reference"), {}
    subscription = data if event in SUBSCRIPTION_EVENTS else data.get("subscription", {})
    if not isinstance(subscription, dict):
        raise ValueError
    code = subscription.get("subscription_code")
    if not isinstance(code, str) or not code.startswith("SUB_") or len(code) > 120:
        raise ValueError
    metadata = {"subscription": code}
    if event in INVOICE_EVENTS:
        for name in ("invoice_code", "period_start", "period_end", "paid_at", "status"):
            value = data.get(name)
            if value is not None and (not isinstance(value, str) or len(value) > 120):
                raise ValueError
            metadata[name] = value
        if type(data.get("paid")) not in {bool, int} or data["paid"] not in (True, False, 0, 1):
            raise ValueError
        if type(data.get("amount")) is not int or data["amount"] < 0:
            raise ValueError
        metadata.update(paid=bool(data["paid"]), amount=data["amount"])
        payment = data.get("transaction") or {}
        if not isinstance(payment, dict):
            raise ValueError
        reference = payment.get("reference", "")
        if not isinstance(reference, str) or len(reference) > 120:
            raise ValueError
        metadata["reference"] = reference
    return code, metadata


def timestamp(value):
    result = parse_datetime(value or "")
    if result is None or timezone.is_naive(result):
        raise ValidationError("Provider timestamp is invalid.")
    return result


def next_month(value):
    # Paystack bills monthly subscriptions begun after day 28 on day 28 thereafter.
    year, month = (value.year + 1, 1) if value.month == 12 else (value.year, value.month + 1)
    return value.replace(year=year, month=month, day=min(value.day, 28))


def match_payment(adapter, checkout, *, customer=None):
    verified = adapter.verify(checkout.provider_reference)
    mapping = ProviderPlan.objects.get(plan=checkout.plan)
    if (
        verified["reference"] != checkout.provider_reference
        or type(verified["amount_minor"]) is not int
        or verified["amount_minor"] != checkout.amount_minor
        or verified["currency"] != checkout.currency
        or verified["plan"] != mapping.code
        or not verified["customer"]
        or (customer is not None and verified["customer"] != customer)
        or (checkout.billing_email and verified["email"].lower() != checkout.billing_email.lower())
    ):
        raise ValidationError("Provider transaction does not match this tenant checkout.")
    paid = verified["occurred_at"]
    if paid is None or timezone.is_naive(paid) or paid > timezone.now() + timedelta(minutes=5):
        raise ValidationError("Provider payment time is invalid.")
    return verified


def initial_payment(event, adapter):
    candidate = Checkout.objects.filter(
        provider="paystack_test", provider_reference=event.reference
    ).first()
    if not candidate:
        # Renewal transactions are linked by invoice events, never by an email guess.
        return "IGNORED"
    Organization.objects.select_for_update().get(pk=candidate.organization_id)
    checkout = Checkout.objects.select_for_update().get(pk=candidate.pk)
    sub = Subscription.objects.select_for_update().get(organization_id=checkout.organization_id)
    if checkout.status in {"SUCCEEDED", "REFUNDED", "CHARGEBACK", "DISPUTED"}:
        return "IGNORED"
    verified = match_payment(adapter, checkout)
    if verified["status"] != "SUCCEEDED":
        raise ValidationError("Provider has not confirmed successful payment.")
    if verified["occurred_at"] < checkout.created_at - timedelta(minutes=5):
        raise ValidationError("Provider payment predates this checkout.")
    customer, _ = ProviderCustomer.objects.get_or_create(
        code=verified["customer"], defaults={"organization_id": checkout.organization_id}
    )
    if customer.organization_id != checkout.organization_id:
        raise ValidationError("Provider customer is already assigned to another organization.")
    checkout.status, checkout.settled_at = "SUCCEEDED", verified["occurred_at"]
    checkout.save(update_fields=["status", "settled_at"])
    if sub.state == "SUSPENDED" or (sub.canceled_at and checkout.created_at <= sub.canceled_at):
        audit(checkout.organization, None, "PAYMENT_REQUIRES_REVIEW", checkout.pk)
        return "PROCESSED"
    from commercial.billing import fits

    fits(checkout.plan, checkout.organization)
    sub.plan, sub.state, sub.provider = checkout.plan, "ACTIVE", "paystack_test"
    sub.provider_customer, sub.provider_subscription = customer.pk, ""
    sub.entitlement_checkout = checkout
    sub.period_ends_at = next_month(checkout.settled_at)
    sub.last_event_at = checkout.settled_at
    sub.grace_ends_at, sub.canceled_at, sub.cancel_at_period_end = None, None, False
    sub.save()
    audit(checkout.organization, None, "PAYSTACK_PAYMENT_CONFIRMED", checkout.pk)
    return "PROCESSED"


def mapped_subscription(adapter, code):
    remote = adapter.subscription(code)
    customer_code = remote.get("customer", {}).get("customer_code")
    plan_code = remote.get("plan", {}).get("plan_code")
    customer = ProviderCustomer.objects.filter(pk=customer_code).first()
    mapping = ProviderPlan.objects.select_related("plan").filter(code=plan_code).first()
    if not customer or not mapping:
        raise ValidationError("Subscription awaits its independently verified initial checkout.")
    Organization.objects.select_for_update().get(pk=customer.organization_id)
    sub = Subscription.objects.select_for_update().get(organization_id=customer.organization_id)
    if (
        remote.get("amount") != int(mapping.plan.monthly_amount * 100)
        or remote.get("plan", {}).get("currency") != mapping.plan.currency
        or remote.get("plan", {}).get("interval") != "monthly"
    ):
        raise ValidationError("Provider subscription terms do not match the immutable plan.")
    row = ProviderSubscription.objects.select_for_update().filter(pk=code).first()
    if row:
        if row.customer_id != customer.pk or row.plan_id != mapping.plan_id:
            raise ValidationError("Provider subscription identity changed.")
    else:
        checkout = sub.entitlement_checkout
        created = timestamp(remote.get("createdAt") or remote.get("created_at"))
        if (
            not checkout
            or checkout.provider != "paystack_test"
            or checkout.status != "SUCCEEDED"
            or checkout.plan_id != mapping.plan_id
            or sub.provider_customer != customer.pk
            or sub.provider_subscription
            or created < checkout.created_at - timedelta(minutes=5)
            or created > checkout.settled_at + timedelta(days=1)
            or created > timezone.now() + timedelta(minutes=5)
        ):
            raise ValidationError("Subscription cannot be linked to this checkout.")
        row = ProviderSubscription.objects.create(
            code=code,
            customer=customer,
            plan=mapping.plan,
            checkout=checkout,
            status=remote.get("status", "unknown"),
        )
        sub.provider_subscription = code
        sub.save(update_fields=["provider_subscription", "updated_at"])
    row.status = remote.get("status", "unknown")
    if row.status not in {
        "active",
        "attention",
        "non-renewing",
        "cancelled",
        "completed",
        "complete",
    }:
        raise ValidationError("Unknown provider subscription status.")
    row.save(update_fields=["status"])
    return sub, row, remote


def recurring_invoice(event, adapter, sub, row):
    data = event.metadata
    start, end = timestamp(data["period_start"]), timestamp(data["period_end"])
    if not data.get("invoice_code") or not start < end <= start + timedelta(days=32):
        raise ValidationError("Invalid provider invoice period.")
    if start > timezone.now() + timedelta(minutes=5) or data["amount"] != int(
        row.plan.monthly_amount * 100
    ):
        raise ValidationError("Invoice is premature or has mismatched terms.")
    if sub.provider_subscription != row.pk:
        return "IGNORED"  # An old subscription can never replace its successor.
    if not data["paid"]:
        if data["status"] not in {"failed", "attention"}:
            return "IGNORED"
        if (
            sub.state in {"ACTIVE", "PAST_DUE"}
            and not sub.cancel_at_period_end
            and sub.period_ends_at
            and start >= sub.period_ends_at - timedelta(minutes=5)
        ):
            sub.state = "PAST_DUE"
            sub.grace_ends_at = sub.period_ends_at + timedelta(days=7)
            sub.save()
            audit(sub.organization, None, "PAYSTACK_RENEWAL_FAILED", data["invoice_code"])
        return "PROCESSED"
    reference = data.get("reference")
    if not reference:
        raise ValidationError("Paid invoice has no verifiable transaction reference.")
    checkout, _ = Checkout.objects.get_or_create(
        provider_reference=reference,
        defaults=dict(
            organization_id=sub.organization_id,
            plan=row.plan,
            provider="paystack_test",
            amount_minor=data["amount"],
            currency=row.plan.currency,
            request_key=uuid5(NAMESPACE_URL, f"paystack-invoice:{reference}"),
        ),
    )
    if (
        checkout.organization_id != sub.organization_id
        or checkout.plan_id != row.plan_id
        or checkout.provider != "paystack_test"
    ):
        raise ValidationError("Invoice transaction belongs to another checkout.")
    if checkout.status in {"REFUNDED", "CHARGEBACK", "DISPUTED"}:
        return "IGNORED"
    verified = match_payment(adapter, checkout, customer=row.customer_id)
    if (
        verified["status"] != "SUCCEEDED"
        or not start - timedelta(minutes=5) <= verified["occurred_at"] < end
    ):
        raise ValidationError("Invoice has no matching successful payment in its period.")
    checkout.status, checkout.settled_at = "SUCCEEDED", verified["occurred_at"]
    checkout.save(update_fields=["status", "settled_at"])
    if (
        sub.state == "SUSPENDED"
        or sub.cancel_at_period_end
        or (sub.period_ends_at and end <= sub.period_ends_at)
    ):
        return "PROCESSED"
    from commercial.billing import fits

    fits(row.plan, sub.organization)
    sub.state, sub.period_ends_at, sub.entitlement_checkout = "ACTIVE", end, checkout
    sub.last_event_at, sub.grace_ends_at = checkout.settled_at, None
    sub.save()
    audit(sub.organization, None, "PAYSTACK_RENEWAL_CONFIRMED", checkout.pk)
    return "PROCESSED"


def reversal(event, adapter):
    refund = event.event_type == "refund.processed"
    path = "refund" if refund else "dispute"
    remote = adapter.request(f"/{path}/{event.metadata['object_id']}")
    if remote.get("domain") != "test":
        raise ValidationError("Only test-provider reversals are supported.")
    payment = remote.get("transaction")
    if type(payment) is int:
        payment = adapter.request(f"/transaction/{payment}")
    if not isinstance(payment, dict) or payment.get("domain") != "test":
        raise ValidationError("Reversal has no verified test transaction.")
    reference = payment.get("reference")
    candidate = Checkout.objects.filter(
        provider="paystack_test", provider_reference=reference
    ).first()
    if not candidate:
        raise ValidationError("Reversal awaits reconciliation of its original checkout.")
    Organization.objects.select_for_update().get(pk=candidate.organization_id)
    checkout = Checkout.objects.select_for_update().get(pk=candidate.pk)
    sub = Subscription.objects.select_for_update().get(organization_id=checkout.organization_id)
    verified = match_payment(adapter, checkout)
    customer = ProviderCustomer.objects.filter(
        code=verified["customer"], organization_id=checkout.organization_id
    ).first()
    if not customer:
        raise ValidationError("Reversal customer does not belong to this tenant.")
    if refund:
        if remote.get("status") != "processed":
            raise ValidationError("Refund processing is not yet confirmed.")
        if (
            type(remote.get("amount")) is not int
            or not 0 < remote["amount"] <= checkout.amount_minor
            or remote.get("currency") != checkout.currency
        ):
            raise ValidationError("Refund amount or currency does not match the checkout.")
    checkout.status = "REFUNDED" if refund else "DISPUTED"
    checkout.save(update_fields=["status"])
    if sub.entitlement_checkout_id == checkout.pk:
        sub.state = "SUSPENDED"
        sub.save(update_fields=["state", "updated_at"])
    audit(
        checkout.organization,
        None,
        "PAYSTACK_REFUND_REVIEW" if refund else "PAYSTACK_DISPUTE_REVIEW",
        checkout.pk,
    )
    # Even a resolved dispute requires operator review; never silently regrant access.
    return "PROCESSED"


def process(event):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Provider events require a locked transaction.")
    adapter = PaystackTestProvider()
    if event.event_type in REVERSAL_EVENTS:
        return reversal(event, adapter)
    if event.event_type in {"charge.success", "operator.reconciliation"}:
        return initial_payment(event, adapter)
    if event.event_type not in SUBSCRIPTION_EVENTS | INVOICE_EVENTS:
        return "IGNORED"
    sub, row, remote = mapped_subscription(adapter, event.metadata["subscription"])
    if sub.provider_subscription != row.pk:
        return "IGNORED"
    if event.event_type in INVOICE_EVENTS:
        return recurring_invoice(event, adapter, sub, row)
    if remote["status"] in {"non-renewing", "cancelled", "completed", "complete"}:
        sub.cancel_at_period_end = True
        sub.canceled_at = sub.canceled_at or timezone.now()
        sub.save()
    # Subscription status alone never grants time or reverses a suspension/cancellation.
    audit(sub.organization, None, "PAYSTACK_SUBSCRIPTION_RECONCILED", row.pk)
    return "PROCESSED"
