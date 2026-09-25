import pytest
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from assets.models import AssetStatus
from maintenance.models import MaintenanceRecord
from transfers.services import assign_asset


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_maintenance_work_order_api_lifecycle_and_accountant_read_only(
    api_client, asset_factory, asset_manager, employee, accountant
):
    asset = asset_factory()
    assert api_client.get("/api/v1/assets/work-orders/").status_code == 401
    api_client.force_authenticate(asset_manager)
    created = api_client.post(
        "/api/v1/assets/work-orders/",
        {
            "asset_id": str(asset.pk),
            "maintenance_type": "CORRECTIVE",
            "priority": "HIGH",
            "description": "Repair pump",
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    order_id = created.data["id"]
    assert created.data["work_order_number"] == "WO-000001"
    api_client.force_authenticate(accountant)
    assert api_client.get("/api/v1/assets/work-orders/?status=OPEN").data["count"] == 1
    assert (
        api_client.post(
            f"/api/v1/assets/work-orders/{order_id}/start/", {}, format="json"
        ).status_code
        == 403
    )
    api_client.force_authenticate(asset_manager)
    assert (
        api_client.post(
            f"/api/v1/assets/work-orders/{order_id}/assign/",
            {"assigned_to_id": str(employee.pk)},
            format="json",
        ).data["status"]
        == "ASSIGNED"
    )
    assert (
        api_client.post(f"/api/v1/assets/work-orders/{order_id}/start/", {}, format="json").data[
            "status"
        ]
        == "IN_PROGRESS"
    )
    cost = api_client.post(
        "/api/v1/assets/maintenance-costs/",
        {
            "work_order_id": order_id,
            "cost_type": "LABOR",
            "description": "Technician",
            "quantity": "2.000",
            "unit_cost": "1500.00",
        },
        format="json",
    )
    assert cost.status_code == 201, cost.data
    assert cost.data["total_cost"] == "3000.00"
    completed = api_client.post(
        f"/api/v1/assets/work-orders/{order_id}/complete/",
        {
            "resolution": "Pump serviced",
            "downtime_minutes": 35,
            "performed_by_id": str(employee.pk),
        },
        format="json",
    )
    assert completed.status_code == 200, completed.data
    assert completed.data["work_order"]["status"] == "COMPLETED"
    assert completed.data["maintenance_record"]["total_cost"] == "3000.00"
    assert (
        api_client.get("/api/v1/assets/maintenance-records/?maintenance_type=CORRECTIVE").data[
            "count"
        ]
        == 1
    )
    asset.refresh_from_db()
    assert asset.status == AssetStatus.ACTIVE
    assert MaintenanceRecord.objects.count() == 1


@pytest.mark.django_db
def test_plan_api_filters_and_employee_scope(
    api_client, asset_factory, asset_manager, employee, department
):
    asset = asset_factory()
    api_client.force_authenticate(asset_manager)
    response = api_client.post(
        "/api/v1/assets/maintenance-plans/",
        {
            "asset_id": str(asset.pk),
            "maintenance_type": "PREVENTIVE",
            "frequency_value": 3,
            "frequency_unit": "MONTHS",
            "next_due_date": "2026-12-01",
            "instructions": "Inspect filters",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    plan_id = response.data["id"]
    listing = api_client.get(
        "/api/v1/assets/maintenance-plans/?active=true&maintenance_type=PREVENTIVE"
    )
    assert listing.status_code == 200, listing.data
    assert listing.data["count"] == 1
    updated = api_client.patch(
        f"/api/v1/assets/maintenance-plans/{plan_id}/", {"active": False}, format="json"
    )
    assert updated.status_code == 200, updated.data
    assert updated.data["active"] is False
    assert api_client.delete(f"/api/v1/assets/maintenance-plans/{plan_id}/").status_code == 405
    api_client.force_authenticate(employee)
    assert api_client.get("/api/v1/assets/maintenance-plans/").data["count"] == 0
    assign_asset(asset_id=asset.pk, actor=asset_manager, assigned_to=employee)
    assert api_client.get("/api/v1/assets/maintenance-plans/").data["count"] == 1


@pytest.mark.django_db
def test_maintenance_api_organization_isolation(
    api_client, asset_manager, other_organization, asset_factory, work_order_factory
):
    order = work_order_factory(asset_factory())
    other_asset_manager = User.objects.create_user(
        "other-manager@example.com",
        "strong-password",
        organization=other_organization,
        role=UserRole.ASSET_MANAGER,
    )
    api_client.force_authenticate(other_asset_manager)
    assert api_client.get("/api/v1/assets/work-orders/").data["count"] == 0
    assert api_client.get(f"/api/v1/assets/work-orders/{order.pk}/").status_code == 404
