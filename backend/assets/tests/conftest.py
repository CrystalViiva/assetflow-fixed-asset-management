from decimal import Decimal

import pytest

from accounts.models import User, UserRole
from assets.models import Acquisition, Asset, AssetCategory
from organizations.models import Department, Location, Organization


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Northwind Nigeria", code="NORTHWIND")


@pytest.fixture
def other_organization(db):
    return Organization.objects.create(name="Contoso Nigeria", code="CONTOSO")


@pytest.fixture
def category(organization):
    return AssetCategory.objects.create(
        organization=organization,
        name="Computer Equipment",
        code="IT-EQUIP",
        default_useful_life_months=48,
        capitalization_threshold=Decimal("50000.00"),
    )


@pytest.fixture
def other_category(other_organization):
    return AssetCategory.objects.create(
        organization=other_organization,
        name="Computer Equipment",
        code="IT-EQUIP",
        default_useful_life_months=36,
    )


@pytest.fixture
def department(organization):
    return Department.objects.create(
        organization=organization, name="Information Technology", code="IT"
    )


@pytest.fixture
def other_department(other_organization):
    return Department.objects.create(organization=other_organization, name="IT", code="IT")


@pytest.fixture
def location(organization):
    return Location.objects.create(organization=organization, name="Lagos HQ", code="LAG-HQ")


@pytest.fixture
def other_location(other_organization):
    return Location.objects.create(organization=other_organization, name="Abuja HQ", code="ABJ-HQ")


@pytest.fixture
def asset_manager(organization):
    return User.objects.create_user(
        "asset.manager@example.com",
        "strong-password",
        organization=organization,
        role=UserRole.ASSET_MANAGER,
    )


@pytest.fixture
def asset_factory(organization, category, asset_manager, department, location):
    def asset_values(asset_tag="AST-000001", **overrides):
        values = {
            "organization": organization,
            "category": category,
            "asset_tag": asset_tag,
            "name": f"Asset {asset_tag}",
            "department": department,
            "location": location,
            "created_by": asset_manager,
            "updated_by": asset_manager,
        }
        values.update(overrides)
        return values

    def make_asset(asset_tag="AST-000001", **overrides):
        return Asset.objects.create(**asset_values(asset_tag, **overrides))

    return make_asset


@pytest.fixture
def asset_instance_factory(organization, category, asset_manager, department, location):
    def make_asset(**overrides):
        values = {
            "organization": organization,
            "category": category,
            "asset_tag": "AST-INSTANCE",
            "name": "Unsaved test asset",
            "department": department,
            "location": location,
            "created_by": asset_manager,
            "updated_by": asset_manager,
        }
        values.update(overrides)
        return Asset(**values)

    return make_asset


@pytest.fixture
def acquisition_factory(asset_manager, asset_factory):
    def make_acquisition(asset=None, **overrides):
        if asset is None:
            asset = asset_factory(
                overrides.pop("asset_tag", "AST-ACQ-001"),
                acquisition_date=overrides.get("acquisition_date"),
            )
        values = {
            "organization": asset_manager.organization,
            "asset": asset,
            "acquisition_date": "2025-01-15",
            "capitalization_date": "2025-02-01",
            "currency": "NGN",
            "purchase_price": Decimal("10000000.00"),
            "freight_cost": Decimal("500000.00"),
            "installation_cost": Decimal("1000000.00"),
            "created_by": asset_manager,
            "updated_by": asset_manager,
        }
        values.update(overrides)
        return Acquisition.objects.create(**values)

    return make_acquisition
