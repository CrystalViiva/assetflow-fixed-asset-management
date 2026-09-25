import pytest
from rest_framework.test import APIClient

from transfers.models import AssetAssignment, AssetTransfer
from transfers.services import assign_asset


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_assignment_api_authentication_role_scope_and_return(
    api_client, asset_factory, asset_manager, employee, accountant, other_organization
):
    asset = asset_factory()
    assignment = assign_asset(asset_id=asset.pk, actor=asset_manager, assigned_to=employee)
    assert api_client.get("/api/v1/assets/assignments/").status_code == 401

    api_client.force_authenticate(employee)
    own = api_client.get("/api/v1/assets/assignments/")
    assert own.status_code == 200
    assert own.data["count"] == 1
    denied = api_client.post(
        "/api/v1/assets/assignments/",
        {"asset_id": str(asset.pk), "assigned_to_id": str(employee.pk)},
        format="json",
    )
    assert denied.status_code == 403

    api_client.force_authenticate(accountant)
    assert api_client.get("/api/v1/assets/assignments/").data["count"] == 1
    assert api_client.get(f"/api/v1/assets/assignments/{assignment.pk}/").status_code == 200

    api_client.force_authenticate(asset_manager)
    response = api_client.post(
        f"/api/v1/assets/assignments/{assignment.pk}/return/", {}, format="json"
    )
    assert response.status_code == 200
    assert response.data["returned_at"] is not None
    assert AssetAssignment.objects.get(pk=assignment.pk).returned_by == asset_manager

    foreign_asset = asset_factory(
        asset_tag="FOREIGN",
        organization=other_organization,
    )
    cross_org = api_client.post(
        "/api/v1/assets/assignments/", {"asset_id": str(foreign_asset.pk)}, format="json"
    )
    assert cross_org.status_code == 400


@pytest.mark.django_db
def test_transfer_api_request_workflow_and_read_only_accountant(
    api_client, asset_factory, asset_manager, accountant, other_department, other_location
):
    asset = asset_factory()
    requested = api_client
    requested.force_authenticate(asset_manager)
    response = requested.post(
        "/api/v1/assets/transfers/",
        {
            "asset_id": str(asset.pk),
            "to_department_id": str(other_department.pk),
            "to_location_id": str(other_location.pk),
            "reason": "Relocation",
            "notes": "New operating site",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    transfer_id = response.data["id"]
    assert response.data["status"] == "REQUESTED"

    api_client.force_authenticate(accountant)
    listing = api_client.get("/api/v1/assets/transfers/?status=REQUESTED&search=AST-MOVE")
    assert listing.status_code == 200
    assert listing.data["count"] == 1
    assert (
        api_client.post(
            f"/api/v1/assets/transfers/{transfer_id}/approve/", {}, format="json"
        ).status_code
        == 403
    )

    api_client.force_authenticate(asset_manager)
    assert (
        api_client.post(f"/api/v1/assets/transfers/{transfer_id}/approve/", {}, format="json").data[
            "status"
        ]
        == "APPROVED"
    )
    complete = api_client.post(
        f"/api/v1/assets/transfers/{transfer_id}/complete/", {}, format="json"
    )
    assert complete.status_code == 200
    assert complete.data["status"] == "COMPLETED"
    assert AssetTransfer.objects.get(pk=transfer_id).completed_by == asset_manager


@pytest.mark.django_db
def test_department_manager_reads_only_in_scope_transfer_and_cannot_mutate(
    api_client, department_manager, asset_factory, transfer_request
):
    transfer = transfer_request()
    api_client.force_authenticate(department_manager)
    visible = api_client.get("/api/v1/assets/transfers/")
    assert visible.status_code == 200
    assert visible.data["count"] == 1
    assert (
        api_client.post(
            f"/api/v1/assets/transfers/{transfer.pk}/approve/", {}, format="json"
        ).status_code
        == 403
    )

    foreign_asset = asset_factory(asset_tag="NO-DEPARTMENT", department=None)
    no_scope_transfer = transfer_request(asset=foreign_asset)
    assert api_client.get("/api/v1/assets/transfers/").data["count"] == 1
    assert api_client.get(f"/api/v1/assets/transfers/{no_scope_transfer.pk}/").status_code == 404


@pytest.mark.django_db
def test_employee_sees_only_transfers_for_currently_assigned_assets(
    api_client, employee, asset_factory, asset_manager, transfer_request
):
    asset = asset_factory()
    assign_asset(asset_id=asset.pk, actor=asset_manager, assigned_to=employee)
    transfer = transfer_request(asset=asset)
    api_client.force_authenticate(employee)
    assert api_client.get("/api/v1/assets/transfers/").data["count"] == 1
    assert api_client.get(f"/api/v1/assets/transfers/{transfer.pk}/").status_code == 200
