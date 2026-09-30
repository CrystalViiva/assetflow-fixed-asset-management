from decimal import Decimal

import pytest

from accounts.models import User, UserRole
from assets.models import Asset, AssetCategory
from organizations.models import Department, Organization


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Report Org", code="RPT")


@pytest.fixture
def other_organization(db):
    return Organization.objects.create(name="Other Report Org", code="ORPT")


@pytest.fixture
def department(organization):
    return Department.objects.create(organization=organization, name="Operations", code="OPS")


@pytest.fixture
def other_department(organization):
    return Department.objects.create(organization=organization, name="Finance", code="FIN")


@pytest.fixture
def foreign_department(other_organization):
    return Department.objects.create(organization=other_organization, name="Other", code="OTHER")


@pytest.fixture
def manager(organization):
    return User.objects.create_user(
        "report.manager@example.test",
        "test-only-password",
        organization=organization,
        role=UserRole.ASSET_MANAGER,
    )


@pytest.fixture
def accountant(organization):
    return User.objects.create_user(
        "report.accountant@example.test",
        "test-only-password",
        organization=organization,
        role=UserRole.ACCOUNTANT,
    )


@pytest.fixture
def department_manager(organization, department):
    return User.objects.create_user(
        "report.department@example.test",
        "test-only-password",
        organization=organization,
        department=department,
        role=UserRole.DEPARTMENT_MANAGER,
    )


@pytest.fixture
def employee(organization):
    return User.objects.create_user(
        "report.employee@example.test",
        "test-only-password",
        organization=organization,
        role=UserRole.EMPLOYEE,
    )


@pytest.fixture
def asset_factory(organization, department, manager):
    def make(asset_tag, *, department_override=None, organization_override=None, **overrides):
        asset_organization = organization_override or organization
        if department_override is None and asset_organization != organization:
            department_override, _ = Department.objects.get_or_create(
                organization=asset_organization, code="RPT", defaults={"name": "Reporting"}
            )
        category, _ = AssetCategory.objects.get_or_create(
            organization=asset_organization,
            code="RPT-CAT",
            defaults={"name": "Report equipment", "default_useful_life_months": 48},
        )
        owner = manager
        if asset_organization != organization:
            owner, _ = User.objects.get_or_create(
                email=f"manager-{asset_organization.pk}@report.example.test",
                defaults={"organization": asset_organization, "role": UserRole.ASSET_MANAGER},
            )
        values = {
            "organization": asset_organization,
            "category": category,
            "asset_tag": asset_tag,
            "name": f"Asset {asset_tag}",
            "department": department_override or department,
            "purchase_cost": Decimal("1234.56"),
            "accumulated_depreciation": Decimal("34.56"),
            "current_book_value": Decimal("1200.00"),
            "created_by": owner,
            "updated_by": owner,
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    return make
