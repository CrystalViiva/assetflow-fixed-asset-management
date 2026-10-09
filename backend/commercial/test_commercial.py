import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import connections
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from accounts.identity_services import accept_ticket, invite, ticket_token
from accounts.models import IdentityTicket, User
from assets.models import Asset, AssetCategory
from assets.services import create_asset
from commercial.billing import cancel, initialize_checkout, process_event, receive_webhook, simulate
from commercial.entitlements import writable
from commercial.models import BillingEvent, Checkout, Plan, Registration, SalesLead, Subscription
from commercial.providers import PaystackTestProvider, provider
from commercial.registration import request_signup, verify_signup
from organizations.models import Organization

pytestmark = pytest.mark.django_db
PASSWORD = "Commercial-synthetic-password-2026!"


@pytest.fixture(autouse=True)
def isolated_settings(settings):
    settings.SELF_SERVICE_ENABLED = True
    settings.BILLING_PROVIDER = "local_sandbox"
    settings.ASSETFLOW_ENV = "test"
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture
def plan():
    return Plan.objects.create(
        code="test-team",
        version=1,
        name="Team",
        monthly_amount=Decimal("100.25"),
        active_users=2,
        registered_assets=1,
        trial_days=14,
    )


@pytest.fixture
def owner(plan):
    request_signup(
        email="owner@example.test",
        company_name="Trial Company",
        currency="NGN",
        timezone_name="Africa/Lagos",
    )
    ticket = IdentityTicket.objects.get(purpose="VERIFY", email="owner@example.test")
    verify_signup(token=ticket_token(ticket), password=PASSWORD, plan_id=plan.pk)
    return User.objects.get(email=ticket.email)


def client(user=None, real=False):
    result = APIClient()
    if user and real:
        response = result.post(
            "/api/v1/auth/token/", {"email": user.email, "password": PASSWORD}, format="json"
        )
        assert response.status_code == 200, response.data
        result.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    elif user:
        result.force_authenticate(user)
    return result


def checkout(owner, plan):
    return initialize_checkout(actor=owner, plan_id=plan.pk, request_key=uuid4())


def test_signup_verification_atomic_resend_and_injection(plan):
    payload = {"email": "new@example.test", "company_name": "New Company", "currency": "NGN"}
    assert (
        client()
        .post("/api/v1/auth/signup/", {**payload, "is_platform_operator": True}, format="json")
        .status_code
        == 400
    )
    assert client().post("/api/v1/auth/signup/", payload, format="json").status_code == 202
    assert not Organization.objects.filter(name="New Company").exists()
    assert not User.objects.filter(email=payload["email"]).exists()
    first = IdentityTicket.objects.get(email=payload["email"])
    assert client().post("/api/v1/auth/signup/", payload, format="json").status_code == 202
    first.refresh_from_db()
    assert first.revoked_at is not None
    ticket = Registration.objects.get(email=payload["email"]).ticket
    completion = {"token": ticket_token(ticket), "password": "123", "plan_id": str(plan.pk)}
    assert (
        client().post("/api/v1/auth/signup/verify/", completion, format="json").status_code == 400
    )
    assert not Organization.objects.filter(name="New Company").exists()
    completion["password"] = PASSWORD
    assert (
        client().post("/api/v1/auth/signup/verify/", completion, format="json").status_code == 200
    )
    assert (
        client().post("/api/v1/auth/signup/verify/", completion, format="json").status_code == 400
    )
    user = User.objects.get(email=payload["email"])
    assert not user.is_platform_operator and not user.is_staff and user.role == "ADMIN"
    assert client(user, real=True).get("/api/v1/dashboard/metrics/").status_code == 200


def test_expired_trial_backend_writes_rejected_reads_exports_retained(owner):
    api = client(owner, real=True)
    Subscription.objects.filter(organization=owner.organization).update(
        trial_ends_at=timezone.now() - timedelta(seconds=1)
    )
    assert (
        api.post(
            "/api/v1/admin/departments/", {"name": "Blocked", "code": "BLOCKED"}, format="json"
        ).status_code
        == 403
    )
    assert api.get("/api/v1/assets/").status_code == 200
    assert api.get("/api/v1/reports/").status_code == 200
    # Reaches payload validation, rather than subscription denial.
    assert api.post("/api/v1/report-exports/", {}, format="json").status_code == 400
    assert api.get("/api/v1/billing/").data["subscription"]["writable"] is False


def test_asset_and_user_limits_enforced_at_services(owner):
    category = AssetCategory.objects.create(
        organization=owner.organization, code="IT", name="IT", default_useful_life_months=36
    )
    create_asset(
        actor=owner,
        data={
            "asset_tag": "ONE",
            "name": "First",
            "category": category,
            "purchase_cost": Decimal("10.01"),
        },
    )
    with pytest.raises(PermissionDenied):
        create_asset(actor=owner, data={"asset_tag": "TWO", "name": "Second", "category": category})
    assert Asset.objects.filter(organization=owner.organization).count() == 1
    first = invite(actor=owner, email="first@example.test", role="EMPLOYEE")
    second = invite(actor=owner, email="second@example.test", role="EMPLOYEE")
    accept_ticket(token=ticket_token(first), purpose="INVITE", password=PASSWORD)
    with pytest.raises(PermissionDenied):
        accept_ticket(token=ticket_token(second), purpose="INVITE", password=PASSWORD)


def test_checkout_idempotency_and_browser_cannot_set_paid(owner, plan):
    key = uuid4()
    first = initialize_checkout(actor=owner, plan_id=plan.pk, request_key=key)
    assert initialize_checkout(actor=owner, plan_id=plan.pk, request_key=key).pk == first.pk
    assert first.amount_minor == 10025
    assert Subscription.objects.get(organization=owner.organization).state == "TRIAL"
    response = client(owner).post(
        "/api/v1/billing/checkout/",
        {"plan_id": str(plan.pk), "request_key": str(uuid4()), "paid": True},
        format="json",
    )
    assert response.status_code == 400
    assert (
        client(owner).patch("/api/v1/billing/", {"state": "ACTIVE"}, format="json").status_code
        == 400
    )


def test_webhook_forgery_replay_dedup_and_delayed_delivery(owner, plan):
    purchase = checkout(owner, plan)
    body = json.dumps(
        {"event": "charge.success", "data": {"reference": purchase.provider_reference}}
    ).encode()
    with pytest.raises(PermissionDenied):
        receive_webhook(body=body, signature="forged")
    event = simulate(actor=owner, checkout_id=purchase.pk, outcome="SUCCEEDED")
    assert Subscription.objects.get(organization=owner.organization).state == "TRIAL"
    assert process_event(event.pk).status == "PROCESSED"
    ends = Subscription.objects.get(organization=owner.organization).period_ends_at
    assert process_event(event.pk).status == "PROCESSED"
    assert Subscription.objects.get(organization=owner.organization).period_ends_at == ends
    signed = provider().signature(body)
    a = receive_webhook(body=body, signature=signed)
    b = receive_webhook(body=body, signature=signed)
    assert a.pk == b.pk
    process_event(a.pk)
    assert Subscription.objects.get(organization=owner.organization).period_ends_at == ends


def test_failure_retry_renewal_grace_and_cancel(owner, plan):
    purchase = checkout(owner, plan)
    process_event(simulate(actor=owner, checkout_id=purchase.pk, outcome="FAILED").pk)
    assert Subscription.objects.get(organization=owner.organization).state == "TRIAL"
    process_event(simulate(actor=owner, checkout_id=purchase.pk, outcome="SUCCEEDED").pk)
    sub = Subscription.objects.get(organization=owner.organization)
    assert sub.state == "ACTIVE" and writable(sub)
    sub.period_ends_at = timezone.now() - timedelta(days=1)
    sub.save()
    renewal = checkout(owner, plan)
    process_event(simulate(actor=owner, checkout_id=renewal.pk, outcome="FAILED").pk)
    sub.refresh_from_db()
    assert sub.state == "PAST_DUE" and writable(sub)
    grace = sub.grace_ends_at
    process_event(simulate(actor=owner, checkout_id=renewal.pk, outcome="FAILED").pk)
    sub.refresh_from_db()
    assert sub.grace_ends_at == grace
    cancel(actor=owner)
    process_event(simulate(actor=owner, checkout_id=renewal.pk, outcome="SUCCEEDED").pk)
    sub.refresh_from_db()
    assert sub.cancel_at_period_end


@pytest.mark.parametrize("outcome", ["REFUNDED", "CHARGEBACK"])
def test_refund_chargeback_and_late_success_cannot_restore_access(owner, plan, outcome):
    purchase = checkout(owner, plan)
    process_event(simulate(actor=owner, checkout_id=purchase.pk, outcome="SUCCEEDED").pk)
    process_event(simulate(actor=owner, checkout_id=purchase.pk, outcome=outcome).pk)
    sub = Subscription.objects.get(organization=owner.organization)
    assert sub.state == "SUSPENDED" and not writable(sub)
    process_event(simulate(actor=owner, checkout_id=purchase.pk, outcome="SUCCEEDED").pk)
    sub.refresh_from_db()
    assert sub.state == "SUSPENDED"


def test_out_of_order_event_rechecks_current_provider_state(owner, plan):
    purchase = checkout(owner, plan)
    failure = simulate(actor=owner, checkout_id=purchase.pk, outcome="FAILED")
    success = simulate(actor=owner, checkout_id=purchase.pk, outcome="SUCCEEDED")
    process_event(success.pk)
    ends = Subscription.objects.get(organization=owner.organization).period_ends_at
    process_event(failure.pk)
    sub = Subscription.objects.get(organization=owner.organization)
    assert sub.state == "ACTIVE" and sub.period_ends_at == ends


def test_cross_tenant_checkout_billing_and_operator_boundaries(owner, plan):
    purchase = checkout(owner, plan)
    other_org = Organization.objects.create(name="Other", code="OTHER")
    other = User.objects.create_user(
        "other@example.test", PASSWORD, organization=other_org, role="ADMIN"
    )
    assert client(other).get("/api/v1/billing/").data["history"] == []
    assert (
        client(other)
        .post(
            f"/api/v1/billing/checkout/{purchase.pk}/simulate/",
            {"outcome": "SUCCEEDED"},
            format="json",
        )
        .status_code
        == 400
    )
    assert client(owner).get("/api/v1/platform/tenants/").status_code == 403
    assert client(owner).get("/api/v1/platform/leads/").status_code == 403
    assert (
        client(owner)
        .post(
            f"/api/v1/platform/tenants/{other_org.pk}/state/",
            {"is_active": False, "reason": "forged"},
            format="json",
        )
        .status_code
        == 403
    )


def test_live_simulation_denied_and_plan_downgrade_preserves_data(owner, plan, settings):
    purchase = checkout(owner, plan)
    settings.ASSETFLOW_ENV = "production"
    with pytest.raises(PermissionDenied):
        simulate(actor=owner, checkout_id=purchase.pk, outcome="SUCCEEDED")
    small = Plan.objects.create(
        code="small", name="Small", monthly_amount=0, active_users=0, registered_assets=0
    )
    with pytest.raises(ValidationError):
        initialize_checkout(actor=owner, plan_id=small.pk, request_key=uuid4())
    assert User.objects.filter(organization=owner.organization).count() == 1


def test_provider_failure_retains_event_for_reconciliation(owner, plan, monkeypatch):
    purchase = checkout(owner, plan)
    event = simulate(actor=owner, checkout_id=purchase.pk, outcome="SUCCEEDED")

    def fail(*args):
        raise OSError("secret provider credentials must not be saved")

    with monkeypatch.context() as patch:
        patch.setattr("commercial.providers.LocalSandboxProvider.verify", fail)
        failed = process_event(event.pk)
        assert failed.status == "FAILED" and failed.last_error == "OSError"
    assert process_event(event.pk).status == "PROCESSED"


def test_paystack_test_adapter_validates_signature_and_remote_record(settings, monkeypatch):
    settings.PAYSTACK_SECRET_KEY = "sk_test_synthetic_not_a_real_credential"
    adapter = PaystackTestProvider()
    body = b'{"event":"charge.success"}'
    assert adapter.verify_signature(body, adapter.signature(body))
    assert not adapter.verify_signature(body + b"x", adapter.signature(body))
    monkeypatch.setattr(
        adapter,
        "request",
        lambda *args: {
            "domain": "test",
            "reference": "af_test",
            "status": "success",
            "amount": 10025,
            "currency": "NGN",
            "paid_at": "2026-10-08T10:00:00Z",
            "customer": {"customer_code": "CUS_test"},
        },
    )
    assert adapter.verify("af_test")["status"] == "SUCCEEDED"
    settings.PAYSTACK_SECRET_KEY = "sk_live_rejected"
    with pytest.raises(ValidationError):
        adapter.secret()


def test_lead_capture_consent_honeypot_dedup_operator_workflow():
    payload = dict(
        request_key=str(uuid4()),
        name="Prospect",
        email="prospect@example.test",
        company="Prospect Co",
        requirements="A synthetic demonstration",
        kind="DEMO",
        consent=True,
    )
    api = client()
    assert (
        api.post("/api/v1/public/leads/", {**payload, "consent": False}, format="json").status_code
        == 400
    )
    assert (
        api.post("/api/v1/public/leads/", {**payload, "website": "spam"}, format="json").status_code
        == 202
    )
    assert SalesLead.objects.count() == 0
    assert api.post("/api/v1/public/leads/", payload, format="json").status_code == 202
    assert api.post("/api/v1/public/leads/", payload, format="json").status_code == 202
    assert SalesLead.objects.count() == 1
    operator = User.objects.create_user("operator@example.test", None, is_platform_operator=True)
    op = client(operator)
    assert op.get("/api/v1/platform/tenants/").data["new_leads"] == 1
    assert (
        op.patch(
            "/api/v1/platform/leads/",
            {"id": str(SalesLead.objects.get().pk), "status": "QUALIFIED"},
            format="json",
        ).status_code
        == 200
    )


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_signup_and_verification(plan):
    def start(_):
        try:
            request_signup(
                email="race@example.test",
                company_name="Race",
                currency="NGN",
                timezone_name="Africa/Lagos",
            )
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(start, range(2)))
    assert Registration.objects.filter(email="race@example.test").count() == 1
    ticket = Registration.objects.get(email="race@example.test").ticket
    token = ticket_token(ticket)

    def verify(_):
        try:
            verify_signup(token=token, password=PASSWORD, plan_id=plan.pk)
            return "ok"
        except ValidationError:
            return "used"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(verify, range(2))) == ["ok", "used"]
    assert Organization.objects.filter(name="Race").count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_webhook_processing_settles_once(owner, plan):
    purchase = checkout(owner, plan)
    event = simulate(actor=owner, checkout_id=purchase.pk, outcome="SUCCEEDED")

    def process(_):
        try:
            return process_event(event.pk).status
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(process, range(2))) == ["PROCESSED", "PROCESSED"]
    assert BillingEvent.objects.filter(status="PROCESSED").count() == 1
    assert Checkout.objects.filter(status="SUCCEEDED").count() == 1


def test_existing_plan_terms_are_immutable(plan):
    from django.core.exceptions import ValidationError as ModelValidationError

    plan.monthly_amount = Decimal("999.00")
    with pytest.raises(ModelValidationError):
        plan.save()
    plan.refresh_from_db()
    assert plan.monthly_amount == Decimal("100.25")


def test_ambiguous_provider_initialization_keeps_reference_for_retry(owner, plan, monkeypatch):
    key = uuid4()

    def fail(*args):
        raise OSError("ambiguous connection failure")

    with monkeypatch.context() as patch:
        patch.setattr("commercial.providers.LocalSandboxProvider.initialize", fail)
        with pytest.raises(ValidationError):
            initialize_checkout(actor=owner, plan_id=plan.pk, request_key=key)
    pending = Checkout.objects.get(request_key=key)
    retried = initialize_checkout(actor=owner, plan_id=plan.pk, request_key=key)
    assert pending.provider_reference == retried.provider_reference
    assert Checkout.objects.filter(request_key=key).count() == 1


def test_managed_activation_resend_and_suspension_invalidate_old_link():
    from accounts.identity_services import provision

    operator = User.objects.create_user(
        "resend-operator@example.test", None, is_platform_operator=True
    )
    record = provision(
        actor=operator, key=uuid4(), name="Managed", code="MANAGED", email="managed@example.test"
    )
    old = ticket_token(record.invitation)
    api = client(operator)
    assert (
        api.post(
            f"/api/v1/platform/tenants/{record.organization_id}/invitation/", {}, format="json"
        ).status_code
        == 200
    )
    with pytest.raises(ValidationError):
        accept_ticket(token=old, purpose="INVITE", password=PASSWORD)
    record.refresh_from_db()
    assert (
        api.post(
            f"/api/v1/platform/tenants/{record.organization_id}/state/",
            {"is_active": False, "reason": "Synthetic hold"},
            format="json",
        ).status_code
        == 200
    )
    assert (
        api.post(
            f"/api/v1/platform/tenants/{record.organization_id}/invitation/", {}, format="json"
        ).status_code
        == 400
    )
    from audit.models import AuditLog

    assert AuditLog.objects.get(action="TENANT_SUSPENDED").metadata["reason"] == "Synthetic hold"
    with pytest.raises(ValidationError):
        accept_ticket(token=ticket_token(record.invitation), purpose="INVITE", password=PASSWORD)


def test_paid_renewal_preserves_unexpired_period_and_suspension_requires_operator(owner, plan):
    first = checkout(owner, plan)
    process_event(simulate(actor=owner, checkout_id=first.pk, outcome="SUCCEEDED").pk)
    previous_end = Subscription.objects.get(organization=owner.organization).period_ends_at
    renewal = checkout(owner, plan)
    process_event(simulate(actor=owner, checkout_id=renewal.pk, outcome="SUCCEEDED").pk)
    sub = Subscription.objects.get(organization=owner.organization)
    assert sub.period_ends_at == previous_end + timedelta(days=30)
    process_event(simulate(actor=owner, checkout_id=renewal.pk, outcome="CHARGEBACK").pk)
    with pytest.raises(PermissionDenied):
        checkout(owner, plan)
