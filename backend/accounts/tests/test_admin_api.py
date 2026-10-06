import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from audit.models import AuditLog
from organizations.models import Department, Organization


@pytest.fixture
def tenant_admin(db):
    org = Organization.objects.create(name="Admin API Org", code="ADM-API")
    return User.objects.create_user(
        "tenant.admin@example.test",
        "Valid-initial-password-2026!",
        organization=org,
        role=UserRole.ADMIN,
    )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_tenant_admin_can_manage_department_location_and_users_with_audit(tenant_admin):
    client = client_for(tenant_admin)
    department_response = client.post(
        reverse("admin-department-list"), {"name": "Finance", "code": "FIN"}, format="json"
    )
    assert department_response.status_code == 201
    department_id = department_response.data["id"]
    location_response = client.post(
        reverse("admin-location-list"),
        {"name": "Main office", "code": "HQ", "city": "Lagos"},
        format="json",
    )
    assert location_response.status_code == 201
    user_response = client.post(
        reverse("admin-user-list"),
        {
            "email": " New.Employee@Example.Test ",
            "password": "Different-strong-password-2026!",
            "role": UserRole.EMPLOYEE,
            "department_id": department_id,
        },
        format="json",
    )
    assert user_response.status_code == 201, user_response.data
    created = User.objects.get(email="new.employee@example.test")
    assert created.check_password("Different-strong-password-2026!")
    assert user_response.data["department_id"] == department_id
    assert "password" not in user_response.data
    audit_rows = list(AuditLog.objects.filter(organization=tenant_admin.organization))
    assert {row.action for row in audit_rows} >= {
        "DEPARTMENT_CREATED",
        "LOCATION_CREATED",
        "USER_CREATED",
    }
    assert "Different-strong-password-2026!" not in str([row.changes for row in audit_rows])
    assert "password" not in str([row.metadata for row in audit_rows]).lower()


@pytest.mark.django_db
def test_user_admin_blocks_self_escalation_last_admin_and_privileged_mass_assignment(tenant_admin):
    client = client_for(tenant_admin)
    url = reverse("admin-user-detail", args=(tenant_admin.pk,))
    assert client.patch(url, {"role": UserRole.EMPLOYEE}, format="json").status_code == 400
    assert client.patch(url, {"is_superuser": True}, format="json").status_code == 400
    assert (
        client.post(
            reverse("admin-user-list"),
            {
                "email": "bad@example.test",
                "password": "Different-strong-password-2026!",
                "role": UserRole.ADMIN,
                "is_staff": True,
            },
            format="json",
        ).status_code
        == 400
    )
    assert tenant_admin.role == UserRole.ADMIN
    assert tenant_admin.is_superuser is False and tenant_admin.is_staff is False


@pytest.mark.django_db
def test_user_password_uses_django_validation_against_the_email_identity(tenant_admin):
    response = client_for(tenant_admin).post(
        reverse("admin-user-list"),
        {
            "email": "new.employee@example.test",
            "password": "new.employee@example.test",
            "role": UserRole.EMPLOYEE,
        },
        format="json",
    )
    assert response.status_code == 400
    assert not User.objects.filter(email="new.employee@example.test").exists()


@pytest.mark.django_db
def test_tenant_admin_scope_role_denials_and_foreign_department_reference(tenant_admin):
    foreign = Organization.objects.create(name="Foreign admin org", code="ADM-FOR")
    foreign_admin = User.objects.create_user(
        "foreign.admin@example.test",
        "Valid-initial-password-2026!",
        organization=foreign,
        role=UserRole.ADMIN,
    )
    foreign_department = Department.objects.create(organization=foreign, name="Foreign", code="F")
    target = User.objects.create_user(
        "target@example.test",
        "Valid-initial-password-2026!",
        organization=tenant_admin.organization,
        role=UserRole.EMPLOYEE,
    )
    client = client_for(tenant_admin)
    assert client.get(reverse("admin-user-detail", args=(foreign_admin.pk,))).status_code == 404
    assert (
        client.patch(
            reverse("admin-user-detail", args=(target.pk,)),
            {"department_id": str(foreign_department.pk)},
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.get(reverse("admin-department-detail", args=(foreign_department.pk,))).status_code
        == 404
    )
    assert (
        client.post(
            reverse("admin-department-list"),
            {"name": "Spoofed", "code": "SP", "organization_id": str(foreign.pk)},
            format="json",
        ).status_code
        == 400
    )
    assert not Department.objects.filter(organization=foreign, code="SP").exists()

    for role in (
        UserRole.ASSET_MANAGER,
        UserRole.ACCOUNTANT,
        UserRole.DEPARTMENT_MANAGER,
        UserRole.EMPLOYEE,
    ):
        user = User.objects.create_user(
            f"{role.lower()}@example.test",
            "Valid-initial-password-2026!",
            organization=tenant_admin.organization,
            role=role,
        )
        assert client_for(user).get(reverse("admin-user-list")).status_code == 403
        assert (
            client_for(user).post(reverse("admin-location-list"), {}, format="json").status_code
            == 403
        )
    platform_user = User.objects.create_superuser(
        "platform@example.test",
        "Valid-initial-password-2026!",
        organization=tenant_admin.organization,
    )
    assert client_for(platform_user).get(reverse("admin-user-list")).status_code == 403


@pytest.mark.django_db
def test_user_admin_paginates_filters_and_exposes_no_mutation_delete(tenant_admin):
    User.objects.create_user(
        "user-one@example.test",
        "Valid-initial-password-2026!",
        organization=tenant_admin.organization,
        role=UserRole.EMPLOYEE,
    )
    client = client_for(tenant_admin)
    page = client.get(reverse("admin-user-list"), {"search": "user-one", "page_size": 1})
    assert page.status_code == 200 and page.data["count"] == 1
    url = reverse("admin-user-detail", args=(page.data["results"][0]["id"],))
    assert client.delete(url).status_code == 405
    assert client.put(url, {"role": UserRole.EMPLOYEE}, format="json").status_code == 405
    assert (
        client.patch(
            url,
            {"organization": str(Organization.objects.create(name="X", code="X").pk)},
            format="json",
        ).status_code
        == 400
    )


@pytest.mark.django_db
def test_admin_cannot_remove_last_active_admin(tenant_admin):
    employee = User.objects.create_user(
        "employee-two@example.test",
        "Valid-initial-password-2026!",
        organization=tenant_admin.organization,
        role=UserRole.EMPLOYEE,
    )
    response = client_for(tenant_admin).patch(
        reverse("admin-user-detail", args=(employee.pk,)), {"role": UserRole.ADMIN}, format="json"
    )
    assert response.status_code == 200
    response = client_for(tenant_admin).patch(
        reverse("admin-user-detail", args=(tenant_admin.pk,)), {"is_active": False}, format="json"
    )
    assert response.status_code == 400
