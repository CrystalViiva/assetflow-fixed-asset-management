import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from accounts.admin import UserAdmin
from accounts.models import User
from organizations.models import Department, Organization


@pytest.mark.django_db
def test_tenant_user_admin_scopes_rows_and_related_choices():
    organization_a = Organization.objects.create(name="Admin A", code="ADMIN-A")
    organization_b = Organization.objects.create(name="Admin B", code="ADMIN-B")
    department_a = Department.objects.create(
        organization=organization_a, name="A Dept", code="A-DEPT"
    )
    department_b = Department.objects.create(
        organization=organization_b, name="B Dept", code="B-DEPT"
    )
    staff = User.objects.create_user(
        "staff-a@example.test", "test-password", organization=organization_a, is_staff=True
    )
    user_a = User.objects.create_user("user-a@example.test", organization=organization_a)
    user_b = User.objects.create_user("user-b@example.test", organization=organization_b)
    model_admin = UserAdmin(User, AdminSite())
    request = RequestFactory().get("/admin/accounts/user/")
    request.user = staff

    assert set(model_admin.get_queryset(request).values_list("pk", flat=True)) == {
        user_a.pk,
        staff.pk,
    }
    department_field = model_admin.formfield_for_foreignkey(
        User._meta.get_field("department"), request
    )
    organization_field = model_admin.formfield_for_foreignkey(
        User._meta.get_field("organization"), request
    )
    assert list(department_field.queryset) == [department_a]
    assert department_b.pk not in set(department_field.queryset.values_list("pk", flat=True))
    assert list(organization_field.queryset) == [organization_a]
    assert "user_permissions" not in {
        field for _, options in model_admin.get_fieldsets(request) for field in options["fields"]
    }
    assert user_b.pk not in set(model_admin.get_queryset(request).values_list("pk", flat=True))


@pytest.mark.django_db
def test_superuser_user_admin_remains_global():
    organization_a = Organization.objects.create(name="Global A", code="GLOBAL-A")
    organization_b = Organization.objects.create(name="Global B", code="GLOBAL-B")
    User.objects.create_user("global-a@example.test", organization=organization_a)
    User.objects.create_user("global-b@example.test", organization=organization_b)
    superuser = User.objects.create_superuser("root@example.test", "test-password")
    model_admin = UserAdmin(User, AdminSite())
    request = RequestFactory().get("/admin/accounts/user/")
    request.user = superuser

    assert model_admin.get_queryset(request).count() == 3
    global_user = User.objects.get(email="global-a@example.test")
    assert "user_permissions" in {
        field
        for _, options in model_admin.get_fieldsets(request, global_user)
        for field in options["fields"]
    }
