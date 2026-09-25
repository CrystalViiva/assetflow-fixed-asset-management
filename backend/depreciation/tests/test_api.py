from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from depreciation.models import AccountingPeriod, DepreciationEntry, DepreciationSchedule
from depreciation.services import generate_depreciation_schedule


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_depreciation_api_authentication_roles_and_tenant_scope(
    api_client, accountant, employee, other_organization, asset_factory
):
    own_asset = asset_factory()
    category = own_asset.category.__class__.objects.create(
        organization=other_organization, name="Other", code="OTHER", default_useful_life_months=12
    )
    from assets.models import Asset

    foreign = Asset.objects.create(
        organization=other_organization,
        category=category,
        asset_tag="FOREIGN-API",
        name="Foreign",
        status="ACTIVE",
        purchase_cost=Decimal("100.00"),
        current_book_value=Decimal("100.00"),
        useful_life_months=12,
        capitalization_date="2025-01-01",
        available_for_use_date="2025-01-01",
    )
    unauthenticated = api_client.get("/api/v1/depreciation/periods/")
    assert unauthenticated.status_code == 401

    api_client.force_authenticate(employee)
    assert api_client.get("/api/v1/depreciation/periods/").status_code == 403

    api_client.force_authenticate(accountant)
    created_period = api_client.post(
        "/api/v1/depreciation/periods/", {"year": 2025, "month": 2}, format="json"
    )
    assert created_period.status_code == 201
    schedule = api_client.post(
        "/api/v1/depreciation/schedules/", {"asset_id": str(own_asset.pk)}, format="json"
    )
    assert schedule.status_code == 201
    foreign_schedule = api_client.post(
        "/api/v1/depreciation/schedules/", {"asset_id": str(foreign.pk)}, format="json"
    )
    assert foreign_schedule.status_code == 400
    entry = api_client.post(
        "/api/v1/depreciation/entries/post/",
        {"asset_id": str(own_asset.pk), "period_id": created_period.data["id"]},
        format="json",
    )
    assert entry.status_code == 201
    assert entry.data["depreciation_amount"] == "166666.67"
    filtered = api_client.get(
        "/api/v1/depreciation/entries/?period=2025-02&method=SLM&search=AST-DEPR"
    )
    assert filtered.status_code == 200
    assert filtered.data["count"] == 1
    date_filtered = api_client.get("/api/v1/depreciation/entries/?period_after=2025-02-01")
    assert date_filtered.status_code == 200
    assert date_filtered.data["count"] == 1
    assert DepreciationSchedule.objects.count() == 1
    assert DepreciationEntry.objects.count() == 1
    assert AccountingPeriod.objects.count() == 1


@pytest.mark.django_db
def test_accountant_can_close_period(api_client, accountant, organization):
    period = AccountingPeriod.objects.create(organization=organization, year=2025, month=2)
    api_client.force_authenticate(accountant)
    response = api_client.post(
        f"/api/v1/depreciation/periods/{period.pk}/close/", {}, format="json"
    )
    assert response.status_code == 200
    assert response.data["status"] == "CLOSED"


@pytest.mark.django_db
def test_department_manager_can_read_own_department_but_cannot_post(
    api_client, organization, department, asset_factory
):
    manager = User.objects.create_user(
        "department.manager@example.com",
        "strong-password",
        organization=organization,
        department=department,
        role=UserRole.DEPARTMENT_MANAGER,
    )
    asset = asset_factory()
    generate_depreciation_schedule(asset_id=asset.pk, actor=manager)
    api_client.force_authenticate(manager)
    response = api_client.get("/api/v1/depreciation/schedules/")
    assert response.status_code == 200
    assert response.data["count"] == 1
    denied = api_client.post(
        "/api/v1/depreciation/periods/", {"year": 2025, "month": 2}, format="json"
    )
    assert denied.status_code == 403

    unassigned_manager = User.objects.create_user(
        "unassigned.manager@example.com",
        "strong-password",
        organization=organization,
        role=UserRole.DEPARTMENT_MANAGER,
    )
    api_client.force_authenticate(unassigned_manager)
    assert api_client.get("/api/v1/depreciation/schedules/").data["count"] == 0
