from decimal import Decimal

import pytest

from accounts.models import User, UserRole
from assets.models import Asset, AssetCategory, AssetStatus
from organizations.models import Department, Organization


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Northwind", code="NW")


@pytest.fixture
def other_organization(db):
    return Organization.objects.create(name="Contoso", code="CT")


@pytest.fixture
def department(organization):
    return Department.objects.create(organization=organization, name="Finance", code="FIN")


@pytest.fixture
def accountant(organization, department):
    return User.objects.create_user(
        "accountant@example.com",
        "strong-password",
        organization=organization,
        department=department,
        role=UserRole.ACCOUNTANT,
    )


@pytest.fixture
def asset_manager(organization, department):
    return User.objects.create_user(
        "manager@example.com",
        "strong-password",
        organization=organization,
        department=department,
        role=UserRole.ASSET_MANAGER,
    )


@pytest.fixture
def employee(organization):
    return User.objects.create_user(
        "employee@example.com", "strong-password", organization=organization
    )


@pytest.fixture
def asset_factory(organization, department):
    def make_asset(**overrides):
        category, _ = AssetCategory.objects.get_or_create(
            organization=organization,
            code="EQUIP",
            defaults={"name": "Equipment", "default_useful_life_months": 60},
        )
        values = {
            "organization": organization,
            "department": department,
            "category": category,
            "asset_tag": "AST-DEPR-001",
            "name": "Test equipment",
            "status": AssetStatus.ACTIVE,
            "acquisition_date": "2025-01-10",
            "capitalization_date": "2025-02-01",
            "available_for_use_date": "2025-02-15",
            "purchase_cost": Decimal("12000000.00"),
            "residual_value": Decimal("2000000.00"),
            "useful_life_months": 60,
            "current_book_value": Decimal("12000000.00"),
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    return make_asset
