from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from assets.models import AssetStatus
from audit.models import AuditLog
from organizations.models import Department


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_asset_list_requires_authentication_and_is_paginated(client, asset_factory):
    for index in range(27):
        asset_factory(f"AST-PAGE-{index:03d}")

    anonymous_response = client.get(reverse("asset-list"))
    assert anonymous_response.status_code == 401

    user = User.objects.get(email="asset.manager@example.com")
    response = authenticated_client(user).get(reverse("asset-list"))

    assert response.status_code == 200
    assert response.data["count"] == 27
    assert len(response.data["results"]) == 25

    limited_response = authenticated_client(user).get(
        reverse("asset-list"), {"page": 2, "page_size": 5}
    )
    assert len(limited_response.data["results"]) == 5


@pytest.mark.django_db
def test_asset_create_retrieve_and_update_use_service_and_related_presentation(
    asset_manager, category, department, location
):
    client = authenticated_client(asset_manager)
    payload = {
        "asset_tag": "AST-API-100",
        "name": "Finance laptop",
        "category_id": str(category.pk),
        "department_id": str(department.pk),
        "location_id": str(location.pk),
        "manufacturer": "Lenovo",
        "model_number": "ThinkPad T14",
        "serial_number": "SN-100",
        "purchase_cost": "1250000.00",
        "residual_value": "50000.00",
        "acquisition_date": "2025-03-10",
        "capitalization_date": "2025-03-10",
    }

    created = client.post(reverse("asset-list"), payload, format="json")

    assert created.status_code == 201
    assert created.data["asset_tag"] == "AST-API-100"
    assert created.data["status"] == AssetStatus.DRAFT
    assert created.data["category_name"] == category.name
    assert created.data["category_code"] == category.code
    assert created.data["department_name"] == department.name
    assert created.data["location_code"] == location.code
    assert created.data["useful_life_months"] == category.default_useful_life_months
    assert created.data["purchase_cost"] == "1250000.00"

    detail_url = reverse("asset-detail", args=[created.data["id"]])
    retrieved = client.get(detail_url)
    assert retrieved.status_code == 200

    updated = client.patch(detail_url, {"name": "Updated finance laptop"}, format="json")
    assert updated.status_code == 200
    assert updated.data["name"] == "Updated finance laptop"
    assert AuditLog.objects.filter(action="ASSET_UPDATED", entity_id=created.data["id"]).exists()

    forbidden_delete = client.delete(detail_url)
    assert forbidden_delete.status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize(
    "foreign_field,fixture_name,payload_field",
    [
        ("category", "other_category", "category_id"),
        ("department", "other_department", "department_id"),
        ("location", "other_location", "location_id"),
    ],
)
def test_asset_api_rejects_cross_organization_relationships(
    request, asset_manager, foreign_field, fixture_name, payload_field
):
    foreign_object = request.getfixturevalue(fixture_name)
    payload = {
        "asset_tag": "AST-CROSS-ORG-API",
        "name": "Invalid organization reference",
        payload_field: str(foreign_object.pk),
    }

    response = authenticated_client(asset_manager).post(
        reverse("asset-list"), payload, format="json"
    )

    assert response.status_code == 400
    assert response.data["success"] is False
    assert payload_field in response.data["error"]["details"]
    assert not AuditLog.objects.filter(action="ASSET_CREATED").exists()


@pytest.mark.django_db
def test_asset_api_returns_validation_envelope_for_invalid_accounting_values(
    asset_manager, category
):
    response = authenticated_client(asset_manager).post(
        reverse("asset-list"),
        {
            "asset_tag": "AST-INVALID-COST",
            "name": "Invalid cost device",
            "category_id": str(category.pk),
            "purchase_cost": "-1.00",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert "purchase_cost" in response.data["error"]["details"]


@pytest.mark.django_db
def test_asset_api_does_not_allow_status_or_ledger_mutation(asset_manager, category):
    response = authenticated_client(asset_manager).post(
        reverse("asset-list"),
        {
            "asset_tag": "AST-READONLY-ACCOUNTING",
            "name": "Read only state device",
            "category_id": str(category.pk),
            "status": AssetStatus.ACTIVE,
            "current_book_value": "100.00",
            "accumulated_depreciation": "10.00",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == AssetStatus.DRAFT
    assert response.data["current_book_value"] == "0.00"
    assert response.data["accumulated_depreciation"] == "0.00"


@pytest.mark.django_db
def test_asset_filters_search_ordering_and_by_tag(asset_manager, asset_factory):
    lower_cost = asset_factory(
        "AST-FILTER-01",
        status=AssetStatus.ACTIVE,
        manufacturer="Acme Systems",
        serial_number="FILTER-SERIAL-ONE",
        acquisition_date=date(2024, 6, 1),
        purchase_cost=Decimal("500000.00"),
    )
    higher_cost = asset_factory(
        "AST-FILTER-02",
        status=AssetStatus.ACTIVE,
        manufacturer="Acme Systems",
        serial_number="FILTER-SERIAL-TWO",
        acquisition_date=date(2025, 1, 1),
        purchase_cost=Decimal("900000.00"),
    )
    asset_factory(
        "AST-FILTER-03",
        status=AssetStatus.DRAFT,
        manufacturer="Other maker",
        acquisition_date=date(2025, 2, 1),
    )
    client = authenticated_client(asset_manager)

    response = client.get(
        reverse("asset-list"),
        {
            "status": "ACTIVE",
            "category__name": lower_cost.category.name,
            "department__name": lower_cost.department.name,
            "location__name": lower_cost.location.name,
            "manufacturer": "acme",
            "acquisition_date_after": "2024-12-01",
            "acquisition_date_before": "2025-12-31",
            "search": "FILTER-SERIAL-TWO",
            "ordering": "-purchase_cost",
        },
    )

    assert response.status_code == 200
    assert [row["id"] for row in response.data["results"]] == [str(higher_cost.pk)]
    ordered = client.get(reverse("asset-list"), {"status": "ACTIVE", "ordering": "-purchase_cost"})
    assert [row["id"] for row in ordered.data["results"]] == [
        str(higher_cost.pk),
        str(lower_cost.pk),
    ]
    assert client.get(reverse("asset-by-tag", args=[lower_cost.asset_tag])).data["id"] == str(
        lower_cost.pk
    )


@pytest.mark.django_db
def test_asset_list_rejects_invalid_status_and_date_range(asset_manager):
    client = authenticated_client(asset_manager)

    invalid_status = client.get(reverse("asset-list"), {"status": "NOT_A_STATUS"})
    reversed_range = client.get(
        reverse("asset-list"),
        {"acquisition_date_after": "2025-01-01", "acquisition_date_before": "2024-01-01"},
    )

    assert invalid_status.status_code == 400
    assert invalid_status.data["error"]["code"] == "VALIDATION_ERROR"
    assert reversed_range.status_code == 400
    assert "acquisition_date" in reversed_range.data["error"]["details"]


@pytest.mark.django_db
def test_asset_and_category_reads_are_organization_scoped(
    asset_manager, asset_factory, other_organization, other_category
):
    own_asset = asset_factory("AST-OWN")
    other_user = User.objects.create_user(
        "other.manager@example.com",
        "strong-password",
        organization=other_organization,
        role=UserRole.ASSET_MANAGER,
    )
    from assets.models import Asset

    other_asset = Asset.objects.create(
        organization=other_organization,
        category=other_category,
        asset_tag="AST-OTHER",
        name="Other organization asset",
    )
    other_client = authenticated_client(other_user)

    own_response = authenticated_client(asset_manager).get(reverse("asset-list"))
    other_response = other_client.get(reverse("asset-list"))
    cross_org_detail = authenticated_client(asset_manager).get(
        reverse("asset-detail", args=[other_asset.pk])
    )
    other_categories = other_client.get(reverse("asset-category-list"))

    assert [item["id"] for item in own_response.data["results"]] == [str(own_asset.pk)]
    assert [item["asset_tag"] for item in other_response.data["results"]] == ["AST-OTHER"]
    assert cross_org_detail.status_code == 404
    assert [item["code"] for item in other_categories.data["results"]] == [other_category.code]


@pytest.mark.django_db
def test_accountant_is_read_only_and_department_manager_is_scoped(
    organization, asset_factory, department
):
    same_department_asset = asset_factory("AST-DEPT-OWN", status=AssetStatus.DRAFT)
    another_department = Department.objects.create(
        organization=organization, name="Finance", code="FIN"
    )
    other_department_asset = asset_factory(
        "AST-DEPT-OTHER", department=another_department, status=AssetStatus.DRAFT
    )
    department_manager = User.objects.create_user(
        "department.manager@example.com",
        "strong-password",
        organization=organization,
        department=department,
        role=UserRole.DEPARTMENT_MANAGER,
    )
    accountant = User.objects.create_user(
        "accountant@example.com",
        "strong-password",
        organization=organization,
        role=UserRole.ACCOUNTANT,
    )

    department_response = authenticated_client(department_manager).get(reverse("asset-list"))
    accountant_response = authenticated_client(accountant).get(reverse("asset-list"))
    accountant_write = authenticated_client(accountant).post(
        reverse("asset-list"),
        {
            "asset_tag": "AST-ACCOUNTANT-WRITE",
            "name": "Denied",
            "category_id": str(same_department_asset.category_id),
        },
        format="json",
    )

    assert [item["id"] for item in department_response.data["results"]] == [
        str(same_department_asset.pk)
    ]
    assert str(other_department_asset.pk) not in {
        item["id"] for item in department_response.data["results"]
    }
    assert accountant_response.data["count"] == 2
    assert accountant_write.status_code == 403


@pytest.mark.django_db
def test_employee_only_reads_active_assets_in_their_organization(organization, asset_factory):
    active_asset = asset_factory("AST-EMPLOYEE-ACTIVE", status=AssetStatus.ACTIVE)
    asset_factory("AST-EMPLOYEE-DRAFT", status=AssetStatus.DRAFT)
    employee = User.objects.create_user(
        "employee@example.com", "strong-password", organization=organization, role=UserRole.EMPLOYEE
    )

    response = authenticated_client(employee).get(reverse("asset-list"))

    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(active_asset.pk)


@pytest.mark.django_db
def test_category_endpoints_support_create_update_and_protect_delete(asset_manager):
    client = authenticated_client(asset_manager)
    list_url = reverse("asset-category-list")
    created = client.post(
        list_url,
        {
            "name": "Vehicles",
            "code": "VEH",
            "default_useful_life_months": 72,
            "default_depreciation_method": "SLM",
            "capitalization_threshold": "250000.00",
        },
        format="json",
    )

    assert created.status_code == 201
    assert created.data["organization_id"] == str(asset_manager.organization_id)

    detail_url = reverse("asset-category-detail", args=[created.data["id"]])
    updated = client.patch(detail_url, {"default_useful_life_months": 84}, format="json")
    assert updated.status_code == 200
    assert updated.data["default_useful_life_months"] == 84
    assert client.delete(detail_url).status_code == 405
