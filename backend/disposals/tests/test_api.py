import pytest
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from disposals.services import create_disposal


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_disposal_api_full_workflow_accounting_snapshot_and_role_controls(
    api_client, asset_factory, asset_manager, approver, accountant, employee
):
    asset = asset_factory()
    assert api_client.get("/api/v1/assets/disposals/").status_code == 401
    api_client.force_authenticate(asset_manager)
    created = api_client.post(
        "/api/v1/assets/disposals/",
        {
            "asset_id": str(asset.pk),
            "disposal_date": "2026-09-25",
            "disposal_method": "SALE",
            "reason": "Sold after replacement",
            "proceeds": "6000.00",
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    assert created.data["currency"] == "NGN"
    assert created.data["status"] == "DRAFT"
    assert created.data["carrying_amount"] is None
    disposal_id = created.data["id"]
    patched = api_client.patch(
        f"/api/v1/assets/disposals/{disposal_id}/", {"proceeds": "6500.00"}, format="json"
    )
    assert patched.status_code == 200, patched.data
    assert patched.data["proceeds"] == "6500.00"
    submitted = api_client.post(
        f"/api/v1/assets/disposals/{disposal_id}/submit/", {}, format="json"
    )
    assert submitted.status_code == 200
    self_approval = api_client.post(
        f"/api/v1/assets/disposals/{disposal_id}/approve/", {}, format="json"
    )
    assert self_approval.status_code == 400
    assert self_approval.data["success"] is False

    api_client.force_authenticate(approver)
    assert (
        api_client.post(f"/api/v1/assets/disposals/{disposal_id}/approve/", {}, format="json").data[
            "status"
        ]
        == "APPROVED"
    )
    completed = api_client.post(
        f"/api/v1/assets/disposals/{disposal_id}/complete/", {}, format="json"
    )
    assert completed.status_code == 200, completed.data
    assert completed.data["status"] == "COMPLETED"
    assert completed.data["capitalized_cost_at_disposal"] == "12000.00"
    assert completed.data["accumulated_depreciation_at_disposal"] == "7000.00"
    assert completed.data["carrying_amount"] == "5000.00"
    assert completed.data["gain_or_loss"] == "1500.00"

    api_client.force_authenticate(accountant)
    filtered = api_client.get("/api/v1/assets/disposals/?status=COMPLETED&gain_or_loss_min=1000")
    assert filtered.status_code == 200, filtered.data
    assert filtered.data["count"] == 1
    assert (
        api_client.post(
            f"/api/v1/assets/disposals/{disposal_id}/cancel/", {}, format="json"
        ).status_code
        == 403
    )
    api_client.force_authenticate(employee)
    assert api_client.get("/api/v1/assets/disposals/").status_code == 403


@pytest.mark.django_db
def test_api_organization_isolation_and_rejected_cancel_workflow(
    api_client, asset_factory, asset_manager, approver, other_organization
):
    disposal = create_disposal(
        actor=asset_manager,
        asset_id=asset_factory().pk,
        disposal_date="2026-09-25",
        disposal_method="WRITE_OFF",
        reason="Test rejection",
        proceeds="0.00",
    )
    api_client.force_authenticate(asset_manager)
    assert (
        api_client.post(
            f"/api/v1/assets/disposals/{disposal.pk}/submit/", {}, format="json"
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            f"/api/v1/assets/disposals/{disposal.pk}/reject/", {"reason": "Denied"}, format="json"
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            f"/api/v1/assets/disposals/{disposal.pk}/complete/", {}, format="json"
        ).status_code
        == 400
    )

    foreign = User.objects.create_user(
        "foreign-manager@example.com",
        "strong-password",
        organization=other_organization,
        role=UserRole.ASSET_MANAGER,
    )
    api_client.force_authenticate(foreign)
    assert api_client.get("/api/v1/assets/disposals/").data["count"] == 0
    assert api_client.get(f"/api/v1/assets/disposals/{disposal.pk}/").status_code == 404
    assert (
        api_client.post(
            "/api/v1/assets/disposals/",
            {
                "asset_id": str(disposal.asset_id),
                "disposal_date": "2026-09-25",
                "disposal_method": "SALE",
                "reason": "Cross org",
                "proceeds": "1.00",
            },
            format="json",
        ).status_code
        == 400
    )
