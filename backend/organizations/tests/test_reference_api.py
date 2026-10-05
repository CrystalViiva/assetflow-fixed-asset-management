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


@pytest.mark.django_db
def test_custodian_reference_is_minimal_paginated_tenant_scoped_and_manager_only():
    own = Organization.objects.create(name="Own", code="OWN-CUST")
    other = Organization.objects.create(name="Other", code="OTHER-CUST")
    department = Department.objects.create(organization=own, name="Operations", code="OPS")
    foreign_department = Department.objects.create(
        organization=other, name="Foreign Operations", code="FOREIGN-OPS"
    )
    manager = User.objects.create_user(
        "manager@example.test", organization=own, role="ASSET_MANAGER"
    )
    own_user = User.objects.create_user(
        "custodian@example.test", organization=own, department=department
    )
    for number in range(24):
        User.objects.create_user(
            f"worker-{number:02}@example.test", organization=own, role="EMPLOYEE"
        )
    User.objects.create_user("inactive@example.test", organization=own, is_active=False)
    inconsistent = User.objects.create_user(
        "legacy@example.test", organization=own, department=foreign_department
    )
    User.objects.create_user("foreign@example.test", organization=other)
    api = APIClient()
    assert api.get(reverse("custodian-list")).status_code == 401
    api.force_authenticate(manager)
    response = api.get(reverse("custodian-list"), {"organization_id": str(other.pk)})
    assert response.status_code == 200
    assert response.data["count"] == 27
    assert len(response.data["results"]) == 25
    assert response.data["next"] is not None
    second_page = api.get(reverse("custodian-list"), {"page": 2}).data["results"]
    assert len(second_page) == 2
    assert {manager.email, own_user.email}.issubset(
        {row["email"] for row in response.data["results"]}
    )
    custodian = next(row for row in response.data["results"] if row["id"] == own_user.pk)
    assert set(custodian) == {"id", "email", "role", "department_id", "department_name"}
    assert custodian["department_id"] == str(department.pk)
    legacy = next(
        row for row in [*response.data["results"], *second_page] if row["id"] == inconsistent.pk
    )
    assert legacy["department_id"] is None
    assert legacy["department_name"] is None
    assert api.post(reverse("custodian-list"), {}, format="json").status_code == 403
    api.force_authenticate(own_user)
    assert api.get(reverse("custodian-list")).status_code == 403
