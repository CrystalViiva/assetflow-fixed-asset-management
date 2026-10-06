from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from assets.models import Acquisition, AcquisitionStatus, Asset, AssetStatus
from audit.models import AuditLog


@pytest.mark.django_db
def test_dashboard_decimal_totals_are_scoped_and_do_not_join_multiply(
    asset_factory, organization, category, asset_manager, department
):
    capitalization_day = timezone.localdate().replace(day=1).isoformat()
    first = asset_factory(
        "DASH-001",
        status=AssetStatus.ACTIVE,
        acquisition_date=capitalization_day,
        capitalization_date=capitalization_day,
        purchase_cost=Decimal("1000.10"),
        accumulated_depreciation=Decimal("100.05"),
        current_book_value=Decimal("900.05"),
    )
    asset_factory(
        "DASH-002",
        status=AssetStatus.ACTIVE,
        acquisition_date=capitalization_day,
        capitalization_date=capitalization_day,
        purchase_cost=Decimal("2000.20"),
        accumulated_depreciation=Decimal("200.10"),
        current_book_value=Decimal("1800.10"),
    )
    asset_factory("DASH-DRAFT", status=AssetStatus.DRAFT, purchase_cost=Decimal("500.00"))
    asset_factory(
        "DASH-DISPOSED",
        status=AssetStatus.DISPOSED,
        acquisition_date=capitalization_day,
        capitalization_date=capitalization_day,
        purchase_cost=Decimal("700.00"),
        current_book_value=Decimal("0.00"),
    )
    for asset, cost in (
        (first, Decimal("1000.10")),
        (Asset.objects.get(asset_tag="DASH-002"), Decimal("2000.20")),
        (Asset.objects.get(asset_tag="DASH-DISPOSED"), Decimal("700.00")),
    ):
        Acquisition.objects.create(
            organization=organization,
            asset=asset,
            acquisition_date=capitalization_day,
            capitalization_date=capitalization_day,
            currency=organization.currency,
            purchase_price=cost,
            status=AcquisitionStatus.CAPITALIZED,
        )
    from depreciation.models import AccountingPeriod, DepreciationEntry, DepreciationSchedule

    period_date = timezone.localdate()
    period = AccountingPeriod.objects.create(
        organization=organization, year=period_date.year, month=period_date.month
    )
    for asset, cost, accumulated, book_value in (
        (first, "1000.10", "100.05", "900.05"),
        (Asset.objects.get(asset_tag="DASH-002"), "2000.20", "200.10", "1800.10"),
    ):
        schedule = DepreciationSchedule.objects.create(
            organization=organization,
            asset=asset,
            method="SLM",
            capitalized_cost=cost,
            depreciable_base=cost,
            residual_value="0.00",
            useful_life_months=36,
            start_date=capitalization_day,
            end_date="2028-12-31",
            periodic_depreciation=accumulated,
        )
        DepreciationEntry.objects.create(
            organization=organization,
            asset=asset,
            schedule=schedule,
            accounting_period=period,
            opening_book_value=cost,
            depreciation_amount=accumulated,
            accumulated_depreciation=accumulated,
            closing_book_value=book_value,
        )
    # Ledger rows define carrying amounts even if a materialized Asset snapshot is stale.
    Asset.objects.filter(pk=first.pk).update(
        current_book_value=Decimal("850.00"), accumulated_depreciation=Decimal("150.00")
    )
    foreign_org = organization.__class__.objects.create(name="Foreign dashboard", code="FDASH")
    foreign_category = category.__class__.objects.create(
        organization=foreign_org, name="Foreign", code="F", default_useful_life_months=12
    )
    Asset.objects.create(
        organization=foreign_org,
        category=foreign_category,
        asset_tag="FOREIGN",
        name="Foreign",
        status=AssetStatus.ACTIVE,
        capitalization_date="2025-01-01",
        purchase_cost=Decimal("999999.99"),
        current_book_value=Decimal("999999.99"),
    )

    # Extra child-domain rows for one asset must not multiply portfolio money.
    from maintenance.models import MaintenanceType, WorkOrder

    WorkOrder.objects.create(
        organization=organization,
        work_order_number="DASH-WO-1",
        asset=first,
        maintenance_type=MaintenanceType.CORRECTIVE,
        description="One",
        requested_by=asset_manager,
    )
    WorkOrder.objects.create(
        organization=organization,
        work_order_number="DASH-WO-2",
        asset=first,
        maintenance_type=MaintenanceType.CORRECTIVE,
        description="Two",
        requested_by=asset_manager,
    )
    AuditLog.objects.create(
        organization=organization,
        user=asset_manager,
        action="ASSET_CAPITALIZED",
        entity_type="ASSET",
        entity_id=str(first.pk),
    )
    client = APIClient()
    client.force_authenticate(asset_manager)
    with CaptureQueriesContext(connection) as captured:
        response = client.get(reverse("dashboard-metrics"))
    assert response.status_code == 200
    assert response.data["currency"] == "NGN"
    assert response.data["portfolio"] == {
        "registered_assets": 4,
        "currently_held_assets": 2,
        "capitalized_assets": 2,
        "disposed_assets": 1,
    }
    assert response.data["financial"]["capitalized_cost"] == "3000.30"
    assert response.data["financial"]["accumulated_depreciation"] == "300.15"
    assert response.data["financial"]["book_value"] == "2700.15"
    assert response.data["financial"]["current_month_posted_depreciation"] == "300.15"
    assert response.data["distributions"]["category"][0]["book_value"] == "2700.15"
    assert response.data["trends"]["capitalizations"] == [
        {"period": timezone.localdate().strftime("%Y-%m"), "amount": "3700.30"}
    ]
    assert response.data["operations"]["open_work_orders"] == 2
    assert response.data["recent_activity"][0]["actor"] == asset_manager.email
    assert len(captured) < 35


@pytest.mark.django_db
def test_department_manager_only_receives_department_scoped_values(
    asset_factory, organization, department, other_department
):
    asset_factory(
        "DASH-OWN",
        department=department,
        status=AssetStatus.ACTIVE,
        capitalization_date="2025-01-01",
        purchase_cost="100.00",
        current_book_value="100.00",
    )
    asset_factory(
        "DASH-OTHER",
        department=other_department,
        status=AssetStatus.ACTIVE,
        capitalization_date="2025-01-01",
        purchase_cost="900.00",
        current_book_value="900.00",
    )
    manager = User.objects.create_user(
        "dashboard.dept@example.test",
        "test-only-password",
        organization=organization,
        department=department,
        role=UserRole.DEPARTMENT_MANAGER,
    )
    client = APIClient()
    client.force_authenticate(manager)
    response = client.get(reverse("dashboard-metrics"))
    assert response.status_code == 200
    assert response.data["scope"] == "department"
    assert response.data["portfolio"]["registered_assets"] == 1
    assert response.data["financial"]["capitalized_cost"] == "100.00"


@pytest.mark.django_db
def test_employee_cannot_read_dashboard(asset_manager, organization):
    employee = User.objects.create_user(
        "dashboard.employee@example.test",
        "test-only-password",
        organization=organization,
        role=UserRole.EMPLOYEE,
    )
    client = APIClient()
    client.force_authenticate(employee)
    assert client.get(reverse("dashboard-metrics")).status_code == 403


@pytest.mark.django_db
def test_dashboard_zero_values_are_exact_strings(asset_manager):
    client = APIClient()
    client.force_authenticate(asset_manager)
    response = client.get(reverse("dashboard-metrics"))
    assert response.status_code == 200
    assert response.data["portfolio"]["registered_assets"] == 0
    assert response.data["financial"]["capitalized_cost"] == "0.00"
    assert response.data["financial"]["book_value"] == "0.00"
