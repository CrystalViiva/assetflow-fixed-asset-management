from datetime import date
from decimal import Decimal
from itertools import count

import pytest

from accounts.models import User, UserRole
from assets.models import Asset, AssetCategory, AssetStatus
from organizations.models import Department, Location, Organization
from verification.models import CampaignScope
from verification.services import create_campaign, start_campaign


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
def foreign_department(other_organization):
    return Department.objects.create(organization=other_organization, name="Finance", code="FIN")


@pytest.fixture
def location(organization):
    return Location.objects.create(organization=organization, name="Lagos", code="LOS")


@pytest.fixture
def other_location(organization):
    return Location.objects.create(organization=organization, name="Abuja", code="ABJ")


@pytest.fixture
def manager(organization):
    return User.objects.create_user(
        "manager@example.com",
        "secret-password",
        organization=organization,
        role=UserRole.ASSET_MANAGER,
    )


@pytest.fixture
def admin_user(organization):
    return User.objects.create_user(
        "admin@example.com", "secret-password", organization=organization, role=UserRole.ADMIN
    )


@pytest.fixture
def accountant(organization):
    return User.objects.create_user(
        "accountant@example.com",
        "secret-password",
        organization=organization,
        role=UserRole.ACCOUNTANT,
    )


@pytest.fixture
def department_manager(organization, department):
    return User.objects.create_user(
        "department@example.com",
        "secret-password",
        organization=organization,
        department=department,
        role=UserRole.DEPARTMENT_MANAGER,
    )


@pytest.fixture
def employee(organization, department):
    return User.objects.create_user(
        "employee@example.com",
        "secret-password",
        organization=organization,
        department=department,
        role=UserRole.EMPLOYEE,
    )


@pytest.fixture
def foreign_manager(other_organization):
    return User.objects.create_user(
        "foreign@example.com",
        "secret-password",
        organization=other_organization,
        role=UserRole.ASSET_MANAGER,
    )


@pytest.fixture
def asset_factory(organization, department, location):
    sequence = count(1)

    def create(**overrides):
        category, _ = AssetCategory.objects.get_or_create(
            organization=organization,
            code="EQUIP",
            defaults={"name": "Equipment", "default_useful_life_months": 60},
        )
        values = {
            "organization": organization,
            "category": category,
            "asset_tag": f"AST-VER-{next(sequence):05d}",
            "name": "Verification fixture asset",
            "department": department,
            "location": location,
            "status": AssetStatus.ACTIVE,
            "acquisition_date": date(2024, 1, 1),
            "capitalization_date": date(2024, 1, 1),
            "available_for_use_date": date(2024, 1, 1),
            "purchase_cost": Decimal("1000.00"),
            "residual_value": Decimal("100.00"),
            "current_book_value": Decimal("1000.00"),
            "accumulated_depreciation": Decimal("0.00"),
            "useful_life_months": 60,
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    return create


@pytest.fixture
def campaign_factory(manager, department, location):
    def create(*, actor=None, scope_type=CampaignScope.ORGANIZATION, **overrides):
        actor = actor or manager
        values = {
            "name": "Annual inventory",
            "description": "Annual physical verification",
            "scope_type": scope_type,
            "start_date": date.today(),
            "due_date": None,
            "department": department if scope_type == CampaignScope.DEPARTMENT else None,
            "location": location if scope_type == CampaignScope.LOCATION else None,
        }
        values.update(overrides)
        return create_campaign(actor=actor, **values)

    return create


@pytest.fixture
def open_campaign(campaign_factory, manager):
    campaign = campaign_factory()
    return start_campaign(campaign_id=campaign.pk, actor=manager)
