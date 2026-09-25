from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from assets.models import AcquisitionStatus, AssetStatus
from assets.services.acquisition import create_acquisition
from audit.models import AuditLog
from organizations.models import Department


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def acquisition_payload(asset, **overrides):
    payload = {
        "asset_id": str(asset.pk),
        "vendor_name": "Abuja Equipment Company",
        "invoice_number": "INV-API-001",
        "reference": "PO-API-001",
        "acquisition_date": "2025-01-15",
        "capitalization_date": "2025-02-01",
        "purchase_price": "10000000.00",
        "freight_cost": "500000.00",
        "installation_cost": "1000000.00",
        "civil_works_cost": "0.00",
        "other_capitalizable_cost": "0.00",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_acquisition_api_create_list_retrieve_update_and_capitalize(
    client, asset_manager, asset_factory
):
    asset = asset_factory("AST-API-ACQ")
    url = reverse("acquisition-list")

    anonymous = client.get(url)
    assert anonymous.status_code == 401

    api = authenticated_client(asset_manager)
    created = api.post(url, acquisition_payload(asset), format="json")
    assert created.status_code == 201
    assert created.data["total_cost"] == "11500000.00"
    assert created.data["currency"] == "NGN"
    assert created.data["asset_tag"] == asset.asset_tag
    assert created.data["status"] == AcquisitionStatus.DRAFT
    assert "ACQUISITION_CREATED" in AuditLog.objects.values_list("action", flat=True)

    detail_url = reverse("acquisition-detail", args=[created.data["id"]])
    listed = api.get(url)
    retrieved = api.get(detail_url)
    assert listed.status_code == 200
    assert listed.data["count"] == 1
    assert retrieved.status_code == 200

    updated = api.patch(detail_url, {"freight_cost": "750000.00"}, format="json")
    assert updated.status_code == 200
    assert updated.data["total_cost"] == "11750000.00"
    assert AuditLog.objects.filter(action="ACQUISITION_UPDATED").exists()

    # Client-supplied lifecycle and derived fields are ignored.
    unchanged = api.patch(
        detail_url,
        {"status": AcquisitionStatus.CAPITALIZED, "total_cost": "1.00"},
        format="json",
    )
    assert unchanged.status_code == 200
    assert unchanged.data["status"] == AcquisitionStatus.DRAFT
    assert unchanged.data["total_cost"] == "11750000.00"

    capitalized = api.post(reverse("acquisition-capitalize", args=[created.data["id"]]))
    assert capitalized.status_code == 200
    assert capitalized.data["status"] == AcquisitionStatus.CAPITALIZED
    asset.refresh_from_db()
    assert asset.status == AssetStatus.ACTIVE
    assert asset.purchase_cost == Decimal("11750000.00")
    assert asset.current_book_value == Decimal("11750000.00")

    repeated = api.post(reverse("acquisition-capitalize", args=[created.data["id"]]))
    assert repeated.status_code == 400
    assert repeated.data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_api_rejects_negative_and_zero_acquisition_cost(asset_manager, asset_factory):
    api = authenticated_client(asset_manager)
    url = reverse("acquisition-list")

    negative = api.post(
        url,
        acquisition_payload(asset_factory("AST-API-NEGATIVE"), freight_cost="-1.00"),
        format="json",
    )
    zero = api.post(
        url,
        acquisition_payload(
            asset_factory("AST-API-ZERO"),
            purchase_price="0.00",
            freight_cost="0.00",
            installation_cost="0.00",
        ),
        format="json",
    )

    assert negative.status_code == 400
    assert "freight_cost" in negative.data["error"]["details"]
    assert zero.status_code == 400
    assert "total_cost" in zero.data["error"]["details"]


@pytest.mark.django_db
def test_api_rejects_capitalization_without_date_and_duplicate_asset_acquisition(
    asset_manager, asset_factory
):
    api = authenticated_client(asset_manager)
    asset = asset_factory("AST-API-INVALID-CAP")
    created = api.post(
        reverse("acquisition-list"),
        acquisition_payload(asset, capitalization_date=None),
        format="json",
    )
    assert created.status_code == 201

    failed_cap = api.post(reverse("acquisition-capitalize", args=[created.data["id"]]))
    assert failed_cap.status_code == 400
    assert "capitalization_date" in failed_cap.data["error"]["details"]

    duplicate = api.post(reverse("acquisition-list"), acquisition_payload(asset), format="json")
    assert duplicate.status_code == 400
    assert "asset" in duplicate.data["error"]["details"]


@pytest.mark.django_db
def test_asset_master_api_cannot_overwrite_accounting_basis_after_capitalization(
    asset_manager, asset_factory
):
    asset = asset_factory("AST-ACTIVE-BASIS", status=AssetStatus.ACTIVE)
    response = authenticated_client(asset_manager).patch(
        reverse("asset-detail", args=[asset.pk]),
        {"purchase_cost": "250000.00"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert "purchase_cost" in response.data["error"]["details"]


@pytest.mark.django_db
def test_api_scopes_acquisitions_to_organization_and_asset_relationships(
    asset_manager,
    asset_factory,
    other_organization,
    other_category,
):
    from assets.models import Asset

    own_asset = asset_factory("AST-ORG-OWN-ACQ")
    foreign_asset = Asset.objects.create(
        organization=other_organization,
        category=other_category,
        asset_tag="AST-ORG-FOREIGN-ACQ",
        name="Foreign organization asset",
    )
    foreign_user = User.objects.create_user(
        "foreign.manager@example.com",
        "strong-password",
        organization=other_organization,
        role=UserRole.ASSET_MANAGER,
    )
    foreign_acquisition = create_acquisition(
        actor=foreign_user,
        data={
            "asset": foreign_asset,
            "acquisition_date": date(2025, 1, 15),
            "purchase_price": Decimal("100.00"),
        },
    )
    api = authenticated_client(asset_manager)

    foreign_asset_create = api.post(
        reverse("acquisition-list"), acquisition_payload(foreign_asset), format="json"
    )
    own_create = api.post(
        reverse("acquisition-list"), acquisition_payload(own_asset), format="json"
    )
    foreign_detail = api.get(reverse("acquisition-detail", args=[foreign_acquisition.pk]))
    foreign_capitalize = api.post(reverse("acquisition-capitalize", args=[foreign_acquisition.pk]))

    assert foreign_asset_create.status_code == 400
    assert own_create.status_code == 201
    assert foreign_detail.status_code == 404
    assert foreign_capitalize.status_code == 404


@pytest.mark.django_db
def test_accountant_is_read_only_employee_denied_and_department_manager_is_scoped(
    organization, asset_manager, asset_factory
):
    own_department = asset_manager.organization.departments.first()
    if own_department is None:
        own_department = Department.objects.create(
            organization=organization, name="Operations", code="OPS"
        )
    visible_asset = asset_factory("AST-DEPT-ACQ-VISIBLE", department=own_department)
    other_department = Department.objects.create(
        organization=organization, name="Finance", code="FIN"
    )
    hidden_asset = asset_factory("AST-DEPT-ACQ-HIDDEN", department=other_department)
    visible_acquisition = create_acquisition(
        actor=asset_manager,
        data={
            "asset": visible_asset,
            "acquisition_date": date(2025, 1, 15),
            "purchase_price": Decimal("100.00"),
        },
    )
    create_acquisition(
        actor=asset_manager,
        data={
            "asset": hidden_asset,
            "acquisition_date": date(2025, 1, 15),
            "purchase_price": Decimal("100.00"),
        },
    )
    dept_manager = User.objects.create_user(
        "dept.acq.manager@example.com",
        "strong-password",
        organization=organization,
        department=own_department,
        role=UserRole.DEPARTMENT_MANAGER,
    )
    accountant = User.objects.create_user(
        "acq.accountant@example.com",
        "strong-password",
        organization=organization,
        role=UserRole.ACCOUNTANT,
    )
    employee = User.objects.create_user(
        "acq.employee@example.com",
        "strong-password",
        organization=organization,
        role=UserRole.EMPLOYEE,
    )
    url = reverse("acquisition-list")

    dept_response = authenticated_client(dept_manager).get(url)
    accountant_api = authenticated_client(accountant)
    accountant_list = accountant_api.get(url)
    accountant_write = accountant_api.post(url, acquisition_payload(visible_asset), format="json")
    employee_response = authenticated_client(employee).get(url)

    assert dept_response.data["count"] == 1
    assert dept_response.data["results"][0]["id"] == str(visible_acquisition.pk)
    assert accountant_list.status_code == 200
    assert accountant_list.data["count"] == 2
    assert accountant_write.status_code == 403
    assert employee_response.status_code == 403


@pytest.mark.django_db
def test_acquisition_filters_and_search_are_database_backed(asset_manager, asset_factory):
    first_asset = asset_factory("AST-FILTER-ACQ-1")
    second_asset = asset_factory("AST-FILTER-ACQ-2")
    first = create_acquisition(
        actor=asset_manager,
        data={
            "asset": first_asset,
            "acquisition_date": date(2024, 1, 15),
            "purchase_price": Decimal("100.00"),
            "invoice_number": "INV-OLDER",
        },
    )
    create_acquisition(
        actor=asset_manager,
        data={
            "asset": second_asset,
            "acquisition_date": date(2025, 1, 15),
            "purchase_price": Decimal("200.00"),
            "invoice_number": "INV-CURRENT",
        },
    )

    response = authenticated_client(asset_manager).get(
        reverse("acquisition-list"),
        {
            "status": AcquisitionStatus.DRAFT,
            "acquisition_date_after": "2024-12-31",
            "invoice_number": "current",
            "search": "AST-FILTER-ACQ-2",
            "ordering": "-total_cost",
        },
    )
    invalid_range = authenticated_client(asset_manager).get(
        reverse("acquisition-list"),
        {"acquisition_date_after": "2025-01-01", "acquisition_date_before": "2024-01-01"},
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] != str(first.pk)
    assert invalid_range.status_code == 400
    assert invalid_range.data["error"]["code"] == "VALIDATION_ERROR"
