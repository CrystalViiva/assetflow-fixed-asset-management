import pytest
from rest_framework.test import APIClient

from verification.models import CampaignScope, ExceptionType, VerificationResult
from verification.services import create_campaign, start_campaign


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_campaign_verification_exception_and_evidence_api_workflow(
    api_client, manager, admin_user, employee, asset_factory, department, location, other_location
):
    asset = asset_factory()
    assert api_client.get("/api/v1/verification/campaigns/").status_code == 401
    api_client.force_authenticate(manager)
    created = api_client.post(
        "/api/v1/verification/campaigns/",
        {"name": "Q4 physical check", "scope_type": "ORGANIZATION", "start_date": "2026-01-01"},
        format="json",
    )
    assert created.status_code == 201, created.data
    campaign_id = created.data["id"]
    assert created.data["expected_asset_count"] == 1
    assert (
        api_client.post(
            f"/api/v1/verification/campaigns/{campaign_id}/start/", {}, format="json"
        ).status_code
        == 200
    )

    observation = api_client.post(
        "/api/v1/verification/records/",
        {
            "campaign_id": campaign_id,
            "asset_id": str(asset.pk),
            "observed_asset_tag": asset.asset_tag,
            "observed_location_id": str(other_location.pk),
            "observed_department_id": str(department.pk),
            "observed_condition": "GOOD",
        },
        format="json",
    )
    assert observation.status_code == 201, observation.data
    assert observation.data["result"] == VerificationResult.LOCATION_MISMATCH
    assert observation.data["exceptions"][0]["exception_type"] == ExceptionType.LOCATION_MISMATCH
    assert str(observation.data["observed_location_id"]) == str(other_location.pk)
    assert (
        api_client.get(
            f"/api/v1/verification/records/?result={VerificationResult.LOCATION_MISMATCH}"
        ).data["count"]
        == 1
    )

    manual_exception = api_client.post(
        "/api/v1/verification/exceptions/",
        {
            "verification_id": observation.data["id"],
            "description": "Reviewer noted an additional issue.",
            "severity": "LOW",
            "exception_type": "LOCATION_MISMATCH",
        },
        format="json",
    )
    assert manual_exception.status_code == 201, manual_exception.data
    assert manual_exception.data["exception_type"] == ExceptionType.OTHER

    exception_id = observation.data["exceptions"][0]["id"]
    assigned = api_client.post(
        f"/api/v1/verification/exceptions/{exception_id}/assign/",
        {"assigned_to_id": str(employee.pk)},
        format="json",
    )
    assert assigned.status_code == 200, assigned.data
    assert (
        api_client.post(
            f"/api/v1/verification/exceptions/{exception_id}/start-review/", {}, format="json"
        ).status_code
        == 200
    )
    resolved = api_client.post(
        f"/api/v1/verification/exceptions/{exception_id}/resolve/",
        {"resolution_notes": "Transfer workflow was completed", "resolution_reference": "TR-42"},
        format="json",
    )
    assert resolved.status_code == 200, resolved.data
    assert resolved.data["status"] == "RESOLVED"

    evidence = api_client.post(
        "/api/v1/verification/evidence/",
        {
            "verification_id": observation.data["id"],
            "exception_id": exception_id,
            "evidence_type": "PHOTO",
            "file_name": "asset.jpg",
            "content_type": "image/jpeg",
            "storage_key": "metadata-only/asset.jpg",
            "description": "Physical label",
        },
        format="json",
    )
    assert evidence.status_code == 201, evidence.data
    assert evidence.data["storage_key"] == "metadata-only/asset.jpg"
    progress = api_client.get(f"/api/v1/verification/campaigns/{campaign_id}/")
    assert progress.data["verified_asset_count"] == 1
    assert progress.data["verification_percentage"] == "100.00"

    api_client.force_authenticate(admin_user)
    completed = api_client.post(
        f"/api/v1/verification/campaigns/{campaign_id}/complete/", {}, format="json"
    )
    assert completed.status_code == 200
    assert completed.data["status"] == "COMPLETED"


@pytest.mark.django_db
def test_department_manager_can_verify_scoped_assets_but_cannot_manage_campaign(
    api_client, manager, department_manager, asset_factory, department, location
):
    asset = asset_factory()
    campaign = create_campaign(
        actor=manager,
        name="Engineering inventory",
        scope_type=CampaignScope.DEPARTMENT,
        department=department,
        start_date="2026-01-01",
    )
    start_campaign(campaign_id=campaign.pk, actor=manager)
    api_client.force_authenticate(department_manager)
    assert api_client.get(f"/api/v1/verification/campaigns/{campaign.pk}/").status_code == 200
    assert (
        api_client.post(
            "/api/v1/verification/campaigns/",
            {"name": "Forbidden", "scope_type": "ORGANIZATION", "start_date": "2026-01-01"},
            format="json",
        ).status_code
        == 403
    )
    response = api_client.post(
        "/api/v1/verification/records/",
        {
            "campaign_id": str(campaign.pk),
            "asset_id": str(asset.pk),
            "observed_asset_tag": asset.asset_tag,
            "observed_location_id": str(location.pk),
            "observed_department_id": str(department.pk),
        },
        format="json",
    )
    assert response.status_code == 201, response.data


@pytest.mark.django_db
def test_accountant_read_only_and_organization_isolation(
    api_client, manager, accountant, foreign_manager, other_organization, asset_factory
):
    asset = asset_factory()
    campaign = create_campaign(
        actor=manager,
        name="Read scope",
        scope_type=CampaignScope.ORGANIZATION,
        start_date="2026-01-01",
    )
    start_campaign(campaign_id=campaign.pk, actor=manager)
    api_client.force_authenticate(manager)
    record = api_client.post(
        "/api/v1/verification/records/",
        {"campaign_id": str(campaign.pk), "asset_id": str(asset.pk), "observed_asset_tag": ""},
        format="json",
    )
    assert record.status_code == 201, record.data
    api_client.force_authenticate(accountant)
    assert api_client.get("/api/v1/verification/records/").status_code == 200
    assert api_client.post("/api/v1/verification/campaigns/", {}, format="json").status_code == 403
    api_client.force_authenticate(foreign_manager)
    assert api_client.get("/api/v1/verification/campaigns/").data["count"] == 0
    assert api_client.get(f"/api/v1/verification/records/{record.data['id']}/").status_code == 404


@pytest.mark.django_db
def test_employee_has_no_verification_access(api_client, employee):
    api_client.force_authenticate(employee)
    assert api_client.get("/api/v1/verification/campaigns/").status_code == 403
