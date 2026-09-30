from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from assets.models import Acquisition
from audit.services import record_event
from reporting.models import ReportSnapshot, ReportSnapshotRow, SnapshotStatus
from reporting.selectors import DEFINITIONS, report_queryset, report_rows
from reporting.services import execute_snapshot, fail_snapshot


@pytest.mark.django_db
def test_live_asset_register_is_paginated_filtered_and_decimal_exact(
    manager, asset_factory, other_organization, foreign_department
):
    first = asset_factory("RPT-001")
    asset_factory("RPT-002", purchase_cost=Decimal("2.10"))
    foreign = asset_factory(
        "RPT-001",
        organization_override=other_organization,
        department_override=foreign_department,
    )
    client = APIClient()
    client.force_authenticate(manager)

    response = client.get("/api/v1/reports/asset_register/?search=RPT-001&page_size=1")
    invalid_status = client.get("/api/v1/reports/asset_register/?status=UNKNOWN_STATUS")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert invalid_status.status_code == 400
    row = response.data["results"][0]
    assert row["id"] == str(first.pk)
    assert row["purchase_cost"] == "1234.56"
    assert row["current_book_value"] == "1200.00"
    assert row["id"] != str(foreign.pk)


@pytest.mark.django_db
def test_report_catalog_and_department_scope_match_domain_access(
    department_manager, department, other_department, asset_factory, employee
):
    own = asset_factory("OWN-001", department_override=department)
    asset_factory("OTHER-001", department_override=other_department)
    client = APIClient()
    client.force_authenticate(department_manager)

    catalog = client.get("/api/v1/reports/")
    response = client.get("/api/v1/reports/asset_register/")
    forbidden_department = client.get(
        f"/api/v1/reports/asset_register/?department={other_department.pk}"
    )

    assert catalog.status_code == 200
    assert "lifecycle_history" not in {row["report_type"] for row in catalog.data}
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(own.pk)
    assert forbidden_department.status_code == 400

    client.force_authenticate(employee)
    assert client.get("/api/v1/reports/").status_code == 403


@pytest.mark.django_db
def test_accountant_catalog_excludes_operational_reports(accountant):
    client = APIClient()
    client.force_authenticate(accountant)

    response = client.get("/api/v1/reports/")

    assert response.status_code == 200
    report_types = {row["report_type"] for row in response.data}
    assert "depreciation" in report_types
    assert "work_orders" not in report_types


@pytest.mark.django_db
def test_accountants_cannot_read_broader_assurance_snapshots(manager, accountant):
    snapshot = ReportSnapshot.objects.create(
        organization=manager.organization,
        requested_by=manager,
        requested_role=manager.role,
        report_type="assurance_findings",
        idempotency_key=uuid4(),
    )
    client = APIClient()
    client.force_authenticate(accountant)

    detail = client.get(f"/api/v1/report-snapshots/{snapshot.pk}/")
    history = client.get("/api/v1/report-snapshots/")

    assert detail.status_code == 403
    assert history.data["count"] == 0


@pytest.mark.django_db
def test_every_catalog_report_selector_has_a_valid_database_projection(manager):
    for report_type, definition in DEFINITIONS.items():
        queryset = report_queryset(report_type, manager.organization_id, manager)
        projected = report_rows(queryset, report_type)
        assert set(projected.query.values_select) == set(definition.fields.values())
        list(projected[:1])


@pytest.mark.django_db
def test_datetime_date_to_includes_the_whole_calendar_day(manager):
    record_event(
        organization=manager.organization,
        user=manager,
        action="REPORT_DATE_BOUNDARY_TEST",
        entity_type="TEST",
        entity_id="same-day",
    )
    client = APIClient()
    client.force_authenticate(manager)

    response = client.get(
        f"/api/v1/reports/lifecycle_history/?date_to={timezone.localdate().isoformat()}"
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["action"] == "REPORT_DATE_BOUNDARY_TEST"


@pytest.mark.django_db(transaction=True)
def test_snapshot_is_idempotent_reproducible_and_preserves_financial_precision(
    manager, asset_factory
):
    asset = asset_factory("SNAP-001")
    Acquisition.objects.create(
        organization=manager.organization,
        asset=asset,
        acquisition_date="2025-01-01",
        currency="NGN",
        purchase_price=Decimal("1234.56"),
        created_by=manager,
        updated_by=manager,
    )
    key = uuid4()
    client = APIClient()
    client.force_authenticate(manager)
    body = {"report_type": "acquisitions", "filters": {}, "idempotency_key": str(key)}
    with patch("reporting.tasks.generate_report_snapshot.delay") as enqueue:
        first = client.post("/api/v1/report-snapshots/", body, format="json")
        duplicate = client.post("/api/v1/report-snapshots/", body, format="json")

    assert first.status_code == 202
    assert duplicate.status_code == 200
    assert first.data["id"] == duplicate.data["id"]
    assert enqueue.call_count == 2

    snapshot = execute_snapshot(snapshot_id=first.data["id"])
    assert snapshot.status == SnapshotStatus.COMPLETED
    assert snapshot.requested_at <= snapshot.as_of <= snapshot.generated_at
    assert snapshot.failed_at is None
    row = snapshot.rows.get().payload
    assert row["purchase_price"] == "1234.56"
    assert row["total_cost"] == "1234.56"
    assert snapshot.summary == {"total_total_cost": "1234.56", "row_count": 1}
    asset.name = "Changed after capture"
    asset.save(update_fields=("name",))
    snapshot_row = snapshot.rows.get()
    snapshot_row.payload["asset_name"] = "tampered"
    with pytest.raises(ValidationError, match="Snapshot rows are immutable"):
        snapshot_row.save()
    with pytest.raises(ValidationError, match="Snapshot rows are immutable"):
        snapshot.rows.all().delete()

    repeated = execute_snapshot(snapshot_id=snapshot.pk)
    assert repeated.status == SnapshotStatus.COMPLETED
    assert repeated.rows.count() == 1
    assert repeated.rows.get().payload["asset_name"] == "Asset SNAP-001"

    rows_response = client.get(f"/api/v1/report-snapshots/{snapshot.pk}/rows/")
    assert rows_response.status_code == 200
    assert rows_response.data["results"][0]["payload"]["total_cost"] == "1234.56"


@pytest.mark.django_db(transaction=True)
def test_snapshot_empty_dataset_completes_and_cross_organization_is_hidden(
    manager, other_organization
):
    from reporting.services import request_snapshot

    with patch("reporting.tasks.generate_report_snapshot.delay"):
        snapshot, created = request_snapshot(
            user=manager,
            report_type="asset_register",
            filters={"search": "no-match"},
            idempotency_key=uuid4(),
        )
    assert created
    completed = execute_snapshot(snapshot_id=snapshot.pk)
    assert completed.status == SnapshotStatus.COMPLETED
    assert completed.row_count == 0
    assert completed.rows.count() == 0

    foreign_client = APIClient()
    from accounts.models import User, UserRole

    foreign_user = User.objects.create_user(
        "foreign-report@example.test",
        "test-only-password",
        organization=other_organization,
        role=UserRole.ASSET_MANAGER,
    )
    foreign_client.force_authenticate(foreign_user)
    assert foreign_client.get(f"/api/v1/report-snapshots/{snapshot.pk}/").status_code == 403


@pytest.mark.django_db(transaction=True)
def test_failed_snapshot_exposes_failure_state_without_partial_rows(
    manager, asset_factory, monkeypatch
):
    import reporting.services as services

    asset_factory("FAIL-001")
    snapshot = ReportSnapshot.objects.create(
        organization=manager.organization,
        requested_by=manager,
        requested_role=manager.role,
        report_type="asset_register",
        idempotency_key=uuid4(),
    )

    def fail_rows(*_args, **_kwargs):
        raise RuntimeError("test failure")

    monkeypatch.setattr(services, "report_rows", fail_rows)
    with pytest.raises(RuntimeError, match="test failure"):
        execute_snapshot(snapshot_id=snapshot.pk)
    assert not ReportSnapshotRow.objects.filter(snapshot=snapshot).exists()

    failed = fail_snapshot(
        snapshot_id=snapshot.pk,
        failure_class="ReportGenerationError",
        message="Snapshot generation failed after retries.",
    )
    assert failed.status == SnapshotStatus.FAILED
    assert failed.failure_class == "ReportGenerationError"
    assert failed.generated_at is None
    assert failed.failed_at is not None
    assert not failed.rows.exists()
