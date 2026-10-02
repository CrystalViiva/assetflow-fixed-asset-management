import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Department, Location, Organization


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,route", [(Department, "department-list"), (Location, "location-list")]
)
def test_reference_lists_are_paginated_tenant_scoped_and_read_only(model, route):
    own = Organization.objects.create(name="Own", code="OWN")
    other = Organization.objects.create(name="Other", code="OTHER")
    user = User.objects.create_user("reference@example.test", organization=own, role="ADMIN")
    for number in range(26):
        model.objects.create(
            organization=own,
            name=f"Reference {number:02}",
            code=f"R{number}",
            is_active=number != 25,
        )
    foreign = model.objects.create(organization=other, name="Foreign", code="FOREIGN")
    api = APIClient()
    assert api.get(reverse(route)).status_code == 401
    api.force_authenticate(user)
    first = api.get(reverse(route), {"organization_id": str(other.pk)})
    assert first.status_code == 200
    assert first.data["count"] == 26
    assert len(first.data["results"]) == 25
    second = api.get(reverse(route), {"page": 2})
    assert len(second.data["results"]) == 1
    row = second.data["results"][0]
    assert set(row) == {"id", "organization_id", "name", "code", "is_active"}
    assert row["organization_id"] == str(own.pk)
    assert row["is_active"] is False
    assert str(foreign.pk) not in {item["id"] for item in first.data["results"]}
    assert api.post(reverse(route), {"name": "Injection"}, format="json").status_code == 405
    assert api.get(reverse(route) + str(foreign.pk) + "/").status_code == 404
    assert len(api.get(reverse(route), {"page_size": 100}).data["results"]) == 26


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["department-list", "location-list"])
def test_references_require_an_organization_for_all_roles(route):
    api = APIClient()
    user = User.objects.create_user("unscoped@example.test", role="ADMIN", is_superuser=True)
    api.force_authenticate(user)
    response = api.get(reverse(route))
    assert response.status_code == 403
    assert response.data["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role", ["ADMIN", "ASSET_MANAGER", "ACCOUNTANT", "DEPARTMENT_MANAGER", "EMPLOYEE"]
)
def test_existing_asset_read_roles_can_discover_tenant_reference_labels(role):
    organization = Organization.objects.create(name="Tenant", code="TENANT")
    user = User.objects.create_user("role@example.test", organization=organization, role=role)
    api = APIClient()
    api.force_authenticate(user)
    for route in ("department-list", "location-list"):
        assert api.get(reverse(route)).status_code == 200
