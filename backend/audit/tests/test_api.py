import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from audit.services import record_event
from organizations.models import Organization


@pytest.fixture
def audit_manager(db):
    organization = Organization.objects.create(name="Audit API Org", code="AUD-API")
    return User.objects.create_user(
        "audit.manager@example.test",
        "test-password",
        organization=organization,
        role=UserRole.ASSET_MANAGER,
    )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_audit_api_is_organization_scoped_filtered_paginated_and_redacts_secrets(audit_manager):
    own = record_event(
        organization=audit_manager.organization,
        user=audit_manager,
        action="ASSET_UPDATED",
        entity_type="ASSET",
        entity_id="asset-123",
        changes={"location": {"from": "A", "to": "B"}, "access_token": "do-not-return"},
        metadata={"nested": [{"password": "do-not-return"}], "source": "api"},
    )
    foreign_org = Organization.objects.create(name="Foreign", code="AUD-FOR")
    record_event(
        organization=foreign_org,
        action="ASSET_UPDATED",
        entity_type="ASSET",
        entity_id="asset-123",
    )

    response = client_for(audit_manager).get(
        reverse("audit-event-list"), {"entity_id": "asset-123"}
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    event = response.data["results"][0]
    assert event["id"] == str(own.pk)
    assert event["actor_email"] == audit_manager.email
    assert event["changes"]["location"] == {"from": "A", "to": "B"}
    assert event["changes"]["access_token"] == "[REDACTED]"
    assert event["metadata"]["nested"] == [{"password": "[REDACTED]"}]
    assert "ip_address" not in event


@pytest.mark.django_db
def test_audit_api_paginates_and_rejects_invalid_filters_and_ordering(audit_manager):
    for index in range(3):
        record_event(
            organization=audit_manager.organization,
            action=f"ACTION_{index}",
            entity_type="ASSET",
            entity_id=str(index),
        )
    client = client_for(audit_manager)

    page = client.get(reverse("audit-event-list"), {"page_size": 2, "ordering": "timestamp"})
    assert page.status_code == 200
    assert page.data["count"] == 3
    assert len(page.data["results"]) == 2
    assert client.get(reverse("audit-event-list"), {"ordering": "metadata"}).status_code == 400
    assert client.get(reverse("audit-event-list"), {"date_from": "not-a-date"}).status_code == 400


@pytest.mark.django_db
def test_audit_api_requires_control_role_and_has_no_mutation_methods(audit_manager):
    employee = User.objects.create_user(
        "audit.employee@example.test",
        "test-password",
        organization=audit_manager.organization,
        role=UserRole.EMPLOYEE,
    )
    client = client_for(audit_manager)
    url = reverse("audit-event-list")
    assert client.post(url, {}, format="json").status_code == 405
    assert client.put(url, {}, format="json").status_code == 405
    assert client.patch(url, {}, format="json").status_code == 405
    assert client.delete(url).status_code == 405
    assert client_for(employee).get(url).status_code == 403


@pytest.mark.django_db
def test_audit_api_requires_authentication():
    assert APIClient().get(reverse("audit-event-list")).status_code == 401
