from decimal import Decimal
from itertools import count

import pytest

from accounts.models import User, UserRole
from assets.models import Asset, AssetCategory, AssetStatus
from organizations.models import Department, Location, Organization


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Northwind", code="NW")


@pytest.fixture
def other_organization(db):
    return Organization.objects.create(name="Contoso", code="CT")


@pytest.fixture
def department(organization):
    return Department.objects.create(organization=organization, name="Engineering", code="ENG")


@pytest.fixture
def location(organization):
    return Location.objects.create(organization=organization, name="Lagos", code="LOS")


@pytest.fixture
def asset_manager(organization):
    return User.objects.create_user(
        "manager@example.com",
        "strong-password",
        organization=organization,
        role=UserRole.ASSET_MANAGER,
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
def other_org_user(other_organization):
    return User.objects.create_user(
        "other@example.com", "strong-password", organization=other_organization
    )


@pytest.fixture
def asset_factory(organization, department, location):
    sequence = count(1)

    def make_asset(**overrides):
        category, _ = AssetCategory.objects.get_or_create(
            organization=organization,
            code="EQUIP",
            defaults={"name": "Equipment", "default_useful_life_months": 60},
        )
        values = {
            "organization": organization,
            "category": category,
            "asset_tag": f"AST-MNT-{next(sequence):04d}",
            "name": "Maintenance test asset",
            "department": department,
            "location": location,
            "status": AssetStatus.ACTIVE,
            "purchase_cost": Decimal("100000.00"),
            "current_book_value": Decimal("100000.00"),
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    return make_asset


@pytest.fixture
def work_order_factory(asset_manager, asset_factory):
    from maintenance.services import create_work_order

    def create(asset=None, **overrides):
        asset = asset or asset_factory()
        values = {"maintenance_type": "CORRECTIVE", "description": "Replace worn belt"}
        values.update(overrides)
        return create_work_order(actor=asset_manager, asset_id=asset.pk, **values)

    return create
