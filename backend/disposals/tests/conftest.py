from datetime import date
from decimal import Decimal
from itertools import count

import pytest

from accounts.models import User, UserRole
from assets.models import Asset, AssetCategory, AssetStatus
from organizations.models import Department, Location, Organization


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Northwind", code="NW", currency="NGN")


@pytest.fixture
def other_organization(db):
    return Organization.objects.create(name="Contoso", code="CT", currency="NGN")


@pytest.fixture
def department(organization):
    return Department.objects.create(organization=organization, name="Engineering", code="ENG")


@pytest.fixture
def other_department(organization):
    return Department.objects.create(organization=organization, name="Finance", code="FIN")


@pytest.fixture
def location(organization):
    return Location.objects.create(organization=organization, name="Lagos", code="LOS")


@pytest.fixture
def asset_manager(organization):
    return User.objects.create_user(
        "requester@example.com",
        "strong-password",
        organization=organization,
        role=UserRole.ASSET_MANAGER,
    )


@pytest.fixture
def approver(organization):
    return User.objects.create_user(
        "approver@example.com", "strong-password", organization=organization, role=UserRole.ADMIN
    )


@pytest.fixture
def accountant(organization):
    return User.objects.create_user(
        "accountant@example.com",
        "strong-password",
        organization=organization,
        role=UserRole.ACCOUNTANT,
    )


@pytest.fixture
def employee(organization, department):
    return User.objects.create_user(
        "employee@example.com",
        "strong-password",
        organization=organization,
        department=department,
        role=UserRole.EMPLOYEE,
    )


@pytest.fixture
def other_user(other_organization):
    return User.objects.create_user(
        "other@example.com",
        "strong-password",
        organization=other_organization,
        role=UserRole.ASSET_MANAGER,
    )


@pytest.fixture
def asset_factory(organization, department, location):
    tags = count(1)

    def make_asset(**overrides):
        category, _ = AssetCategory.objects.get_or_create(
            organization=organization,
            code="EQUIP",
            defaults={"name": "Equipment", "default_useful_life_months": 60},
        )
        values = {
            "organization": organization,
            "category": category,
            "asset_tag": f"AST-DSP-{next(tags):04d}",
            "name": "Disposal test asset",
            "department": department,
            "location": location,
            "status": AssetStatus.ACTIVE,
            "acquisition_date": date(2020, 1, 1),
            "capitalization_date": date(2020, 1, 1),
            "available_for_use_date": date(2020, 1, 1),
            "purchase_cost": Decimal("12000.00"),
            "residual_value": Decimal("2000.00"),
            "accumulated_depreciation": Decimal("7000.00"),
            "current_book_value": Decimal("5000.00"),
            "useful_life_months": 60,
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    return make_asset


@pytest.fixture
def disposal_factory(asset_manager, asset_factory):
    from disposals.services import create_disposal

    def create(asset=None, **overrides):
        asset = asset or asset_factory()
        values = {
            "disposal_date": date.today(),
            "disposal_method": "SALE",
            "reason": "Asset sold after replacement",
            "proceeds": Decimal("6000.00"),
        }
        values.update(overrides)
        return create_disposal(actor=asset_manager, asset_id=asset.pk, **values)

    return create


@pytest.fixture
def approved_disposal(disposal_factory, asset_manager, approver):
    from disposals.services import approve_disposal, submit_disposal

    disposal = disposal_factory()
    submit_disposal(disposal_id=disposal.pk, actor=asset_manager)
    return approve_disposal(disposal_id=disposal.pk, actor=approver)
