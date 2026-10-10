"""Official Paystack-shaped test contracts; no merchant network or live credentials."""

import copy
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import connections
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from accounts.models import User
from commercial.billing import cancel, initialize_checkout, process_event, receive_webhook
from commercial.models import (
    BillingEvent,
    Checkout,
    Plan,
    ProviderCustomer,
    ProviderPlan,
    ProviderSubscription,
    Subscription,
)
from commercial.paystack import next_month
from commercial.providers import PaystackTestProvider
from organizations.models import Organization

pytestmark = pytest.mark.django_db


@pytest.fixture
def gateway(settings, monkeypatch):
    settings.BILLING_PROVIDER = "paystack_test"
    settings.PAYSTACK_SECRET_KEY = "sk_test_synthetic_contract_only"
    settings.ASSETFLOW_ENV = "test"
    plan = Plan.objects.create(
        code="provider-team", name="Provider Team", monthly_amount=Decimal("100.25")
    )
    ProviderPlan.objects.create(plan=plan, code="PLN_testteam")
    org = Organization.objects.create(name="Provider tenant", code="PROVIDER")
    owner = User.objects.create_user("owner@example.test", None, role="ADMIN", organization=org)
    sub = Subscription.objects.create(
        organization=org, owner=owner, plan=plan, billing_email=owner.email
    )
    anchor = timezone.now() - timedelta(days=35)
    remote = {
        "domain": "test",
        "subscription_code": "SUB_testteam",
        "status": "active",
        "amount": 10025,
        "createdAt": anchor.isoformat(),
        "email_token": "private-token",
        "customer": {"customer_code": "CUS_testteam"},
        "plan": {"plan_code": "PLN_testteam", "interval": "monthly", "currency": "NGN"},
    }
    state = dict(
        owner=owner, plan=plan, sub=sub, remote=remote, charges={}, calls=[], anchor=anchor
    )

    def request(self, path, data=None, **kwargs):
        state["calls"].append((path, data))
        if path.startswith("/plan/"):
            return dict(
                domain="test",
                plan_code="PLN_testteam",
                amount=10025,
                currency="NGN",
                interval="monthly",
            )
        if path == "/transaction/initialize":
            assert re.fullmatch(r"[A-Za-z0-9.=-]+", data["reference"])
            assert data["plan"] == "PLN_testteam" and data["channels"] == ["card"]
            state["charges"][data["reference"]] = {
                "domain": "test",
                "reference": data["reference"],
                "status": "success",
                "amount": 10025,
                "currency": "NGN",
                "paid_at": anchor.isoformat(),
                "plan_object": {"plan_code": "PLN_testteam"},
                "customer": {"customer_code": "CUS_testteam", "email": data["email"]},
            }
            return {"authorization_url": "https://checkout.paystack.com/synthetic"}
        if path.startswith("/transaction/verify/"):
            return copy.deepcopy(state["charges"][path.rsplit("/", 1)[-1]])
        if path.startswith("/subscription/SUB_"):
            return copy.deepcopy(remote)
        if path == "/subscription/disable":
            if state.get("cancel_fails"):
                raise OSError("provider unavailable")
            assert data == {"code": "SUB_testteam", "token": "private-token"}
            remote["status"] = "non-renewing"
            return {}
        if path in {"/refund/17", "/dispute/17"}:
            return copy.deepcopy(state["reversal"])
        raise AssertionError(path)

    monkeypatch.setattr(PaystackTestProvider, "request", request)
    checkout = initialize_checkout(actor=owner, plan_id=plan.pk, request_key=uuid4())
    Checkout.objects.filter(pk=checkout.pk).update(created_at=anchor - timedelta(minutes=1))
    checkout.refresh_from_db()
    state["checkout"] = checkout
    return state


def receive(kind, data):
    body = json.dumps({"event": kind, "data": data}).encode()
    return receive_webhook(body=body, signature=PaystackTestProvider().signature(body))


def activate(gateway):
    event = receive(
        "charge.success", {"domain": "test", "reference": gateway["checkout"].provider_reference}
    )
    assert process_event(event.pk).status == "PROCESSED"
    event = receive("subscription.create", gateway["remote"])
    assert process_event(event.pk).status == "PROCESSED"
    gateway["sub"].refresh_from_db()


def invoice(gateway, *, paid=True):
    start = next_month(gateway["anchor"])
    end = next_month(start)
    ref = "renewal-reference"
    gateway["charges"][ref] = dict(
        domain="test",
        reference=ref,
        status="success",
        amount=10025,
        currency="NGN",
        paid_at=start.isoformat(),
        plan_object={"plan_code": "PLN_testteam"},
        customer={"customer_code": "CUS_testteam", "email": gateway["owner"].email},
    )
    return {
        "domain": "test",
        "invoice_code": "INV_renewal",
        "amount": 10025,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "paid_at": start.isoformat() if paid else None,
        "paid": paid,
        "status": "success" if paid else "failed",
        "subscription": gateway["remote"],
        "transaction": {"reference": ref} if paid else {},
        "authorization": {"authorization_code": "AUTH_neverpersist", "last4": "1234"},
    }


def test_initial_payment_mapping_event_order_and_private_data(gateway):
    early = receive("subscription.create", gateway["remote"])
    assert process_event(early.pk).status == "FAILED"
    assert not ProviderSubscription.objects.exists()
    activate(gateway)
    assert process_event(early.pk).status == "PROCESSED"
    assert gateway["sub"].provider_subscription == "SUB_testteam"
    assert gateway["sub"].period_ends_at == next_month(gateway["anchor"])
    assert ProviderSubscription.objects.get().checkout_id == gateway["checkout"].pk
    assert "private-token" not in json.dumps(list(BillingEvent.objects.values("metadata")))
    api = APIClient()
    api.force_authenticate(gateway["owner"])
    assert api.get("/api/v1/billing/").status_code == 200


def test_renewal_replay_failure_grace_and_recovery(gateway):
    activate(gateway)
    failure = receive("invoice.payment_failed", invoice(gateway, paid=False))
    assert process_event(failure.pk).status == "PROCESSED"
    sub = gateway["sub"]
    sub.refresh_from_db()
    assert sub.state == "PAST_DUE" and sub.grace_ends_at == sub.period_ends_at + timedelta(days=7)
    success = invoice(gateway)
    event = receive("invoice.update", success)
    assert process_event(event.pk).status == "PROCESSED"
    sub.refresh_from_db()
    assert sub.state == "ACTIVE" and sub.period_ends_at.isoformat() == success["period_end"]
    assert sub.grace_ends_at is None
    assert process_event(event.pk).status == "PROCESSED"
    replay = receive("invoice.update", dict(reversed(list(success.items()))))
    assert process_event(replay.pk).status == "PROCESSED"
    sub.refresh_from_db()
    assert sub.period_ends_at.isoformat() == success["period_end"]
    assert Checkout.objects.filter(status="SUCCEEDED").count() == 2
    assert "AUTH_neverpersist" not in json.dumps(list(BillingEvent.objects.values("metadata")))
    # Late failed invoice cannot shorten or extend a later earned period.
    delayed = invoice(gateway, paid=False)
    delayed["invoice_code"] = "INV_delayed"
    assert process_event(receive("invoice.payment_failed", delayed).pk).status == "PROCESSED"
    sub.refresh_from_db()
    assert sub.state == "ACTIVE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("domain", "live"),
        ("amount", 10024),
        ("currency", "USD"),
        ("plan_object", {"plan_code": "PLN_foreign"}),
        ("customer", {"customer_code": "CUS_other", "email": "other@example.test"}),
    ],
)
def test_provider_mismatch_cannot_grant_access(gateway, field, value):
    gateway["charges"][gateway["checkout"].provider_reference][field] = value
    event = receive(
        "charge.success", {"domain": "test", "reference": gateway["checkout"].provider_reference}
    )
    assert process_event(event.pk).status == "FAILED"
    gateway["sub"].refresh_from_db()
    assert gateway["sub"].state == "TRIAL"


def test_customer_and_invoice_cannot_cross_tenants(gateway):
    other = Organization.objects.create(name="Other", code="OTHER")
    ProviderCustomer.objects.create(code="CUS_testteam", organization=other)
    event = receive(
        "charge.success", {"domain": "test", "reference": gateway["checkout"].provider_reference}
    )
    assert process_event(event.pk).status == "FAILED"
    assert gateway["sub"].state == "TRIAL"
    ProviderCustomer.objects.filter(organization=other).delete()  # Test fixture only.
    activate(gateway)
    payload = invoice(gateway)
    Checkout.objects.create(
        organization=other,
        plan=gateway["plan"],
        provider="paystack_test",
        provider_reference="renewal-reference",
        amount_minor=10025,
        currency="NGN",
        request_key=uuid4(),
    )
    assert process_event(receive("invoice.update", payload).pk).status == "FAILED"
    gateway["sub"].refresh_from_db()
    assert gateway["sub"].period_ends_at == next_month(gateway["anchor"])


def test_cancellation_requires_remote_confirmation_and_preserves_history(gateway):
    activate(gateway)
    gateway["cancel_fails"] = True
    with pytest.raises(ValidationError, match="not confirmed"):
        cancel(actor=gateway["owner"])
    gateway["sub"].refresh_from_db()
    assert not gateway["sub"].cancel_at_period_end
    gateway["cancel_fails"] = False
    cancel(actor=gateway["owner"])
    assert (
        process_event(receive("subscription.not_renew", gateway["remote"]).pk).status == "PROCESSED"
    )
    gateway["sub"].refresh_from_db()
    assert gateway["sub"].cancel_at_period_end
    end = gateway["sub"].period_ends_at
    assert process_event(receive("invoice.update", invoice(gateway)).pk).status == "PROCESSED"
    gateway["sub"].refresh_from_db()
    assert gateway["sub"].period_ends_at == end
    assert (
        Checkout.objects.count() == 2
        and Organization.objects.filter(pk=gateway["owner"].organization_id).exists()
    )


def test_pending_checkout_and_active_recurring_contract_cannot_duplicate(gateway):
    with pytest.raises(ValidationError, match="pending provider checkout"):
        cancel(actor=gateway["owner"])
    with pytest.raises(ValidationError):
        initialize_checkout(actor=gateway["owner"], plan_id=gateway["plan"].pk, request_key=uuid4())


def test_paid_checkout_awaiting_mapping_cannot_create_second_subscription(gateway):
    event = receive(
        "charge.success", {"domain": "test", "reference": gateway["checkout"].provider_reference}
    )
    assert process_event(event.pk).status == "PROCESSED"
    with pytest.raises(ValidationError, match="mapping is pending"):
        initialize_checkout(actor=gateway["owner"], plan_id=gateway["plan"].pk, request_key=uuid4())
    activate(gateway)
    with pytest.raises(ValidationError):
        initialize_checkout(actor=gateway["owner"], plan_id=gateway["plan"].pk, request_key=uuid4())


def test_forged_signature_and_malformed_or_live_events_rejected(gateway):
    with pytest.raises(PermissionDenied):
        receive_webhook(body=b"{}", signature="forged")
    for data in ({"domain": "live"}, {"domain": "test", "subscription": []}):
        with pytest.raises(ValidationError):
            receive("invoice.update", data)
    assert not BillingEvent.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_distinct_renewal_deliveries_settle_once(gateway):
    activate(gateway)
    payload = invoice(gateway)
    events = [
        receive("invoice.update", payload),
        receive("invoice.update", dict(reversed(list(payload.items())))),
    ]

    def work(event):
        try:
            return process_event(event.pk).status
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(work, events)) == ["PROCESSED", "PROCESSED"]
    gateway["sub"].refresh_from_db()
    assert gateway["sub"].period_ends_at.isoformat() == payload["period_end"]
    assert Checkout.objects.count() == 2


def test_suspension_is_not_reversed_by_paid_invoice(gateway):
    activate(gateway)
    Subscription.objects.filter(pk=gateway["sub"].pk).update(state="SUSPENDED")
    assert process_event(receive("invoice.update", invoice(gateway)).pk).status == "PROCESSED"
    gateway["sub"].refresh_from_db()
    assert gateway["sub"].state == "SUSPENDED"


@pytest.mark.parametrize(
    "kind", ["refund.processed", "charge.dispute.create", "charge.dispute.resolve"]
)
def test_remote_refunds_and_disputes_suspend_without_erasing_records(gateway, kind):
    activate(gateway)
    cancel(actor=gateway["owner"])
    gateway["reversal"] = dict(
        domain="test",
        status="processed" if kind == "refund.processed" else "resolved",
        amount=10025,
        currency="NGN",
        transaction={"domain": "test", "reference": gateway["checkout"].provider_reference},
    )
    event = receive(kind, {"id": 17})
    assert process_event(event.pk).status == "PROCESSED"
    gateway["sub"].refresh_from_db()
    assert gateway["sub"].state == "SUSPENDED"
    assert Checkout.objects.count() == 1 and ProviderSubscription.objects.count() == 1
    assert process_event(receive("invoice.update", invoice(gateway)).pk).status == "PROCESSED"
    gateway["sub"].refresh_from_db()
    assert gateway["sub"].state == "SUSPENDED"


def test_unconfirmed_or_live_refund_cannot_change_access(gateway):
    activate(gateway)
    gateway["reversal"] = {"domain": "live"}
    event = receive("refund.processed", {"id": 17})
    assert process_event(event.pk).status == "FAILED"
    gateway["sub"].refresh_from_db()
    assert gateway["sub"].state == "ACTIVE"


def test_operator_can_retry_exhausted_subscription_event(gateway):
    from django.core.management import call_command

    event = receive("subscription.create", gateway["remote"])
    assert process_event(event.pk).status == "FAILED"
    BillingEvent.objects.filter(pk=event.pk).update(attempts=8)
    with pytest.raises(PermissionDenied):
        call_command("reconcile_billing_event", event.pk, operator=gateway["owner"].email)
    payment = receive(
        "charge.success", {"domain": "test", "reference": gateway["checkout"].provider_reference}
    )
    assert process_event(payment.pk).status == "PROCESSED"
    operator = User.objects.create_user(
        "provider-operator@example.test", None, is_platform_operator=True
    )
    call_command("reconcile_billing_event", event.pk, operator=operator.email)
    event.refresh_from_db()
    assert event.status == "PROCESSED" and event.attempts == 1
