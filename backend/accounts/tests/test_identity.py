from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core import mail
from django.db import close_old_connections, connections
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.identity_services import (
    accept_ticket,
    deliver_pending,
    invite,
    provision,
    ticket_token,
)
from accounts.models import IdentityDelivery, IdentityTicket, User
from organizations.models import Department, Organization

pytestmark = pytest.mark.django_db
PASSWORD = "Strong-random-customer-2026!"


@pytest.fixture(autouse=True)
def email_settings(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def operator():
    return User.objects.create_user("operator@example.test", PASSWORD, is_platform_operator=True)


@pytest.fixture
def admin():
    org = Organization.objects.create(name="First company", code="FIRST")
    return User.objects.create_user("admin@example.test", PASSWORD, organization=org, role="ADMIN")


def client(user=None):
    result = APIClient()
    if user:
        result.force_authenticate(user)
    return result


def test_bootstrap_operator_cannot_browse_tenant_domains(operator):
    operator.is_superuser = True
    operator.role = "ADMIN"
    operator.save()
    api = client(operator)
    for path in ("assets/", "dashboard/metrics/", "admin/users/", "billing/", "audit/events/"):
        assert api.get(f"/api/v1/{path}").status_code == 403, path


def test_managed_provision_activation_login_invite_and_isolation(operator):
    values = dict(key=uuid4(), name="Customer", code="CUSTOMER", email="owner@example.test")
    record = provision(actor=operator, **values)
    assert provision(actor=operator, **values).pk == record.pk
    assert not record.organization.is_active
    assert not User.objects.filter(email=values["email"]).exists()
    assert deliver_pending() == 1
    assert len(mail.outbox) == 1
    token = mail.outbox[0].body.split("token=")[1].split()[0]
    result = client().post(
        "/api/v1/auth/invitations/accept/", {"token": token, "password": PASSWORD}, format="json"
    )
    assert result.status_code == 200, result.data
    owner = User.objects.get(email=values["email"])
    assert owner.role == "ADMIN" and not owner.is_platform_operator and not owner.is_staff
    assert owner.organization.is_active
    result = client().post(
        "/api/v1/auth/token/", {"email": owner.email, "password": PASSWORD}, format="json"
    )
    assert result.status_code == 200, result.data
    authenticated = client()
    authenticated.credentials(HTTP_AUTHORIZATION=f"Bearer {result.data['access']}")
    assert authenticated.get("/api/v1/dashboard/metrics/").status_code == 200
    assert (
        authenticated.post(
            "/api/v1/admin/invitations/",
            {"email": "colleague@example.test", "role": "ACCOUNTANT"},
            format="json",
        ).status_code
        == 202
    )
    colleague = IdentityTicket.objects.get(email="colleague@example.test")
    accept_ticket(token=ticket_token(colleague), purpose="INVITE", password=PASSWORD)
    assert User.objects.get(email=colleague.email).role == "ACCOUNTANT"
    other_org = Organization.objects.create(name="Other", code="OTHER")
    other = User.objects.create_user(
        "other@example.test", PASSWORD, organization=other_org, role="ADMIN"
    )
    assert client(other).get("/api/v1/admin/invitations/").data == []
    assert (
        client(other)
        .post(f"/api/v1/admin/invitations/{colleague.pk}/revoke/", {}, format="json")
        .status_code
        == 404
    )
    assert client(other).get(f"/api/v1/admin/users/{owner.pk}/").status_code == 404


@pytest.mark.parametrize("state", ["expired", "revoked", "used", "forged", "weak"])
def test_invitation_rejects_unsafe_acceptance(admin, state):
    ticket = invite(actor=admin, email="new@example.test", role="EMPLOYEE")
    token = ticket_token(ticket)
    if state == "expired":
        ticket.expires_at = timezone.now() - timedelta(seconds=1)
    if state == "revoked":
        ticket.revoked_at = timezone.now()
    if state == "used":
        ticket.consumed_at = timezone.now()
    ticket.save()
    if state == "forged":
        token += "bad"
    response = client().post(
        "/api/v1/auth/invitations/accept/",
        {"token": token, "password": "123" if state == "weak" else PASSWORD},
        format="json",
    )
    assert response.status_code == 400
    assert not User.objects.filter(email=ticket.email).exists()


def test_reset_generic_one_use_and_invalidates_access_refresh(admin):
    anonymous = client()
    login = anonymous.post(
        "/api/v1/auth/token/", {"email": admin.email, "password": PASSWORD}, format="json"
    ).data
    exists = anonymous.post("/api/v1/auth/password-reset/", {"email": admin.email}, format="json")
    absent = anonymous.post(
        "/api/v1/auth/password-reset/", {"email": "missing@example.test"}, format="json"
    )
    assert exists.status_code == absent.status_code == 202 and exists.data == absent.data
    ticket = IdentityTicket.objects.get(purpose="RESET")
    token = ticket_token(ticket)
    payload = {"token": token, "password": "Another-strong-password-2026!"}
    assert (
        anonymous.post("/api/v1/auth/password-reset/complete/", payload, format="json").status_code
        == 200
    )
    assert (
        anonymous.post("/api/v1/auth/password-reset/complete/", payload, format="json").status_code
        == 400
    )
    anonymous.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    assert anonymous.get("/api/v1/auth/me/").status_code == 401
    assert (
        client()
        .post("/api/v1/auth/token/refresh/", {"refresh": login["refresh"]}, format="json")
        .status_code
        == 401
    )


def test_operator_boundary_org_injection_and_foreign_department(admin):
    actor = client(admin)
    values = dict(key=str(uuid4()), name="Forbidden", code="FORBIDDEN", email="owner@example.test")
    assert actor.post("/api/v1/platform/provision/", values, format="json").status_code == 403
    other = Organization.objects.create(name="Other", code="OTHER")
    dept = Department.objects.create(organization=other, name="Other", code="OTHER")
    for extra in (
        {"is_platform_operator": True},
        {"organization": str(other.pk)},
        {"department_id": str(dept.pk)},
    ):
        response = actor.post(
            "/api/v1/admin/invitations/",
            {"email": "x@example.test", "role": "ADMIN", **extra},
            format="json",
        )
        assert response.status_code == 400
    admin.role = "EMPLOYEE"
    admin.save()
    assert (
        actor.post(
            "/api/v1/admin/invitations/",
            {"email": "x@example.test", "role": "ADMIN"},
            format="json",
        ).status_code
        == 403
    )


def test_delivery_failure_retry_and_revoked_suppression(admin, monkeypatch):
    ticket = invite(actor=admin, email="new@example.test", role="EMPLOYEE")

    def fail(*args, **kwargs):
        raise OSError("secret SMTP message must never be persisted")

    with monkeypatch.context() as patch:
        patch.setattr("accounts.identity_services.send_mail", fail)
        assert deliver_pending() == 0
    delivery = IdentityDelivery.objects.get(ticket=ticket)
    assert delivery.last_error == "OSError" and delivery.sent_at is None
    delivery.next_attempt_at = timezone.now()
    delivery.save()
    assert deliver_pending() == 1
    assert deliver_pending() == 0
    invite(actor=admin, email="revoked@example.test", role="EMPLOYEE")
    revoked = IdentityTicket.objects.get(email="revoked@example.test")
    revoked.revoked_at = timezone.now()
    revoked.save()
    assert deliver_pending() == 0


def test_throttle_is_shared_and_suspension_blocks_active_session(admin):
    anonymous = client()
    result = anonymous.post(
        "/api/v1/auth/token/", {"email": admin.email, "password": PASSWORD}, format="json"
    )
    anonymous.credentials(HTTP_AUTHORIZATION=f"Bearer {result.data['access']}")
    admin.organization.is_active = False
    admin.organization.save()
    assert anonymous.get("/api/v1/auth/me/").status_code == 401
    for _ in range(20):
        assert (
            client()
            .post("/api/v1/auth/password-reset/", {"email": "missing@example.test"}, format="json")
            .status_code
            == 202
        )
    assert (
        client()
        .post("/api/v1/auth/password-reset/", {"email": "missing@example.test"}, format="json")
        .status_code
        == 429
    )


def test_forwarded_client_address_is_only_accepted_from_trusted_proxy(settings):
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory

    from accounts.throttles import IdentityThrottle

    settings.TRUSTED_PROXY_NETWORKS = ["10.20.0.0/24"]

    class LoginProbe:
        pass

    factory = APIRequestFactory()
    limiter = IdentityThrottle()
    limiter.limit = 1
    for remote, forwarded, expected in [
        ("192.0.2.1", "198.51.100.1", True),
        ("192.0.2.1", "198.51.100.2", False),
        ("10.20.0.2", "198.51.100.1", True),
        ("10.20.0.2", "198.51.100.2", True),
        ("10.20.0.2", "198.51.100.2", False),
    ]:
        request = Request(factory.post("/", REMOTE_ADDR=remote, HTTP_X_REAL_IP=forwarded))
        assert limiter.allow_request(request, LoginProbe()) is expected


@pytest.mark.django_db(transaction=True)
def test_concurrent_invitation_acceptance_creates_one_account(admin):
    ticket = invite(actor=admin, email="racing@example.test", role="EMPLOYEE")
    token = ticket_token(ticket)

    def accept(_):
        close_old_connections()
        try:
            return (
                client()
                .post(
                    "/api/v1/auth/invitations/accept/",
                    {"token": token, "password": PASSWORD},
                    format="json",
                )
                .status_code
            )
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(accept, range(2))) == [200, 400]
    assert User.objects.filter(email=ticket.email).count() == 1
