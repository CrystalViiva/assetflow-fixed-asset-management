from datetime import date
from decimal import Decimal
from itertools import count
from unittest.mock import patch

import pytest

from accounts.models import User, UserRole
from assets.models import Asset, AssetCategory, AssetCondition, AssetStatus
from organizations.models import Department, Location, Organization


@pytest.fixture(autouse=True)
def no_live_continuations():
    with patch("assurance.tasks.execute_assurance_run.apply_async"):
        yield


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Assurance Org", code="ASR", currency="NGN")


@pytest.fixture
def other_organization(db):
    return Organization.objects.create(name="Other Org", code="OTH", currency="NGN")


@pytest.fixture
def department(organization):
    return Department.objects.create(organization=organization, name="Operations", code="OPS")


@pytest.fixture
def other_department(organization):
    return Department.objects.create(organization=organization, name="Finance", code="FIN")


@pytest.fixture
def foreign_department(other_organization):
    return Department.objects.create(
        organization=other_organization, name="Foreign department", code="FDEP"
    )


@pytest.fixture
def location(organization):
    return Location.objects.create(organization=organization, name="Lagos depot", code="LAG")


@pytest.fixture
def other_location(organization):
    return Location.objects.create(organization=organization, name="Abuja depot", code="ABJ")


@pytest.fixture
def manager(organization):
    return User.objects.create_user(
        "assurance-manager@example.test",
        "test-only-password",
        organization=organization,
        role=UserRole.ASSET_MANAGER,
    )


@pytest.fixture
def admin_user(organization):
    return User.objects.create_user(
        "assurance-admin@example.test",
        "test-only-password",
        organization=organization,
        role=UserRole.ADMIN,
    )


@pytest.fixture
def accountant(organization):
    return User.objects.create_user(
        "assurance-accountant@example.test",
        "test-only-password",
        organization=organization,
        role=UserRole.ACCOUNTANT,
    )


@pytest.fixture
def department_manager(organization, department):
    return User.objects.create_user(
        "assurance-department@example.test",
        "test-only-password",
        organization=organization,
        department=department,
        role=UserRole.DEPARTMENT_MANAGER,
    )


@pytest.fixture
def employee(organization):
    return User.objects.create_user(
        "assurance-employee@example.test",
        "test-only-password",
        organization=organization,
        role=UserRole.EMPLOYEE,
    )


@pytest.fixture
def foreign_manager(other_organization):
    return User.objects.create_user(
        "foreign-manager@example.test",
        "test-only-password",
        organization=other_organization,
        role=UserRole.ASSET_MANAGER,
    )


@pytest.fixture
def asset_factory(organization, department, location):
    sequence = count(1)

    def make(**overrides):
        category, _ = AssetCategory.objects.get_or_create(
            organization=organization,
            code="ASSURANCE-EQUIP",
            defaults={"name": "Assurance equipment", "default_useful_life_months": 60},
        )
        values = {
            "organization": organization,
            "category": category,
            "asset_tag": f"AST-ASR-{next(sequence):05d}",
            "name": "Assurance fixture asset",
            "department": department,
            "location": location,
            "status": AssetStatus.ACTIVE,
            "condition": AssetCondition.GOOD,
            "acquisition_date": date(2022, 1, 1),
            "capitalization_date": date(2022, 1, 1),
            "available_for_use_date": date(2022, 1, 1),
            "purchase_cost": Decimal("1000.00"),
            "residual_value": Decimal("100.00"),
            "current_book_value": Decimal("1000.00"),
            "accumulated_depreciation": Decimal("0.00"),
            "useful_life_months": 60,
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    return make


@pytest.fixture
def campaign_factory(manager, department, location):
    from verification.models import CampaignScope
    from verification.services import create_campaign, start_campaign

    def make(*, actor=None, scope_type=CampaignScope.ORGANIZATION, **overrides):
        actor = actor or manager
        values = {
            "name": "Assurance physical count",
            "scope_type": scope_type,
            "start_date": date.today(),
            "department": department if scope_type == CampaignScope.DEPARTMENT else None,
            "location": location if scope_type == CampaignScope.LOCATION else None,
        }
        values.update(overrides)
        campaign = create_campaign(actor=actor, **values)
        return start_campaign(campaign_id=campaign.pk, actor=actor)

    return make


@pytest.fixture
def observation_factory(manager, department, location):
    from verification.models import PhysicalCondition
    from verification.services import create_verification

    def make(campaign, asset=None, **overrides):
        values = {
            "actor": manager,
            "campaign_id": campaign.pk,
            "observed_asset_tag": asset.asset_tag if asset else "UNREGISTERED-ASSET",
            "observed_department": department,
            "observed_location": location,
            "observed_condition": PhysicalCondition.GOOD,
        }
        values.update(overrides)
        if asset is not None:
            values["asset_id"] = asset.pk
        return create_verification(**values)

    return make
