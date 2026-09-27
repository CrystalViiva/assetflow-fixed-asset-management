from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from assurance.models import AssuranceFinding, FindingType
from assurance.services import create_run, execute_run


@pytest.mark.django_db
def test_api_execute_filter_paginate_and_resolve(manager, asset_factory):
    asset_factory(current_book_value=Decimal("900.00"))
    asset_factory(current_book_value=Decimal("800.00"))
    client = APIClient()
    client.force_authenticate(manager)
    created = client.post("/api/v1/assurance/runs/", {"run_type": "FULL"}, format="json")
    assert created.status_code == 201
    run_id = created.data["id"]
    executed = client.post(f"/api/v1/assurance/runs/{run_id}/execute/", {}, format="json")
    assert executed.status_code == 200
    assert executed.data["status"] == "COMPLETED"

    response = client.get(
        "/api/v1/assurance/findings/?finding_type=BOOK_VALUE_EXCEPTION&page_size=1"
    )
    assert response.status_code == 200
    assert response.data["count"] == 2
    assert len(response.data["results"]) == 1
    assert response.data["next"] is not None
    finding = AssuranceFinding.objects.filter(
        last_detected_run_id=run_id, finding_type=FindingType.BOOK_VALUE_EXCEPTION
    ).first()
    reviewed = client.post(f"/api/v1/assurance/findings/{finding.pk}/review/", {}, format="json")
    assert reviewed.status_code == 200
    resolved = client.post(
        f"/api/v1/assurance/findings/{finding.pk}/resolve/",
        {"resolution_notes": "Reviewed supporting ledger"},
        format="json",
    )
    assert resolved.status_code == 200
    assert resolved.data["status"] == "RESOLVED"
    summary = client.get("/api/v1/assurance/summary/")
    assert summary.status_code == 200
    assert summary.data["findings_resolved"] == 1


@pytest.mark.django_db
def test_api_cross_organization_assets_and_runs_are_not_visible(
    manager, foreign_manager, asset_factory
):
    asset_factory(current_book_value=Decimal("900.00"))
    run = create_run(actor=manager, run_type="FULL")
    execute_run(run_id=run.pk, actor=manager)
    client = APIClient()
    client.force_authenticate(foreign_manager)
    assert client.get("/api/v1/assurance/runs/").data["count"] == 0
    assert client.get("/api/v1/assurance/findings/").data["count"] == 0
    assert client.get(f"/api/v1/assurance/runs/{run.pk}/").status_code == 404


@pytest.mark.django_db
def test_accountant_only_sees_financial_findings(manager, accountant, asset_factory):
    asset_factory(current_book_value=Decimal("900.00"))
    run = execute_run(
        run_id=create_run(actor=manager, run_type="FULL").pk,
        actor=manager,
    )
    assert AssuranceFinding.objects.filter(
        last_detected_run=run, finding_type=FindingType.BOOK_VALUE_EXCEPTION
    ).exists()
    client = APIClient()
    client.force_authenticate(accountant)
    response = client.get("/api/v1/assurance/findings/")
    assert response.status_code == 200
    assert {row["finding_type"] for row in response.data["results"]} == {
        "BOOK_VALUE_EXCEPTION",
        "DEPRECIATION_EXCEPTION",
    }


@pytest.mark.django_db
def test_employee_has_no_assurance_access(employee):
    client = APIClient()
    client.force_authenticate(employee)
    assert client.get("/api/v1/assurance/runs/").status_code == 403
    assert (
        client.post("/api/v1/assurance/runs/", {"run_type": "FULL"}, format="json").status_code
        == 403
    )


@pytest.mark.django_db
def test_department_manager_sees_findings_only_for_their_department(
    manager, department_manager, asset_factory, other_department
):
    asset_factory(current_book_value=Decimal("900.00"))
    asset_factory(department=other_department, current_book_value=Decimal("900.00"))
    run = create_run(actor=manager, run_type="FULL")
    execute_run(run_id=run.pk, actor=manager)
    client = APIClient()
    client.force_authenticate(department_manager)

    findings = client.get("/api/v1/assurance/findings/?finding_type=BOOK_VALUE_EXCEPTION")

    assert findings.status_code == 200
    assert findings.data["count"] == 1
    assert findings.data["results"][0]["department_name"] == department_manager.department.name
