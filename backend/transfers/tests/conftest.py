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
def other_department(organization):
    return Department.objects.create(organization=organization, name="Finance", code="FIN")


@pytest.fixture
def other_org_department(other_organization):
    return Department.objects.create(organization=other_organization, name="Operations", code="OPS")


@pytest.fixture
def location(organization):
    return Location.objects.create(organization=organization, name="Lagos", code="LOS")


@pytest.fixture
def other_location(organization):
    return Location.objects.create(organization=organization, name="Abuja", code="ABV")


@pytest.fixture
def other_org_location(other_organization):
    return Location.objects.create(organization=other_organization, name="London", code="LON")


@pytest.fixture
def asset_manager(organization):
    return User.objects.create_user(
        "asset.manager@example.com",
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
def department_manager(organization, department):
    return User.objects.create_user(
        "department.manager@example.com",
        "strong-password",
        organization=organization,
        department=department,
        role=UserRole.DEPARTMENT_MANAGER,
    )


@pytest.fixture
def other_org_user(other_organization):
    return User.objects.create_user(
        "other@example.com", "strong-password", organization=other_organization
    )


@pytest.fixture
def asset_factory(organization, department, location):
    def make_asset(**overrides):
        category, _ = AssetCategory.objects.get_or_create(
            organization=organization,
            code="EQUIP",
            defaults={"name": "Equipment", "default_useful_life_months": 60},
        )
        values = {
            "organization": organization,
            "category": category,
            "asset_tag": "AST-MOVE-001",
            "name": "Movable equipment",
            "department": department,
            "location": location,
            "status": AssetStatus.ACTIVE,
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    return make_asset


@pytest.fixture
def transfer_request(asset_manager, asset_factory, other_department, other_location):
    from transfers.services import request_transfer

    def make_transfer(asset=None, **overrides):
        if asset is None:
            asset = asset_factory()
        values = {
            "asset_id": asset.pk,
            "actor": asset_manager,
            "to_department": other_department,
            "to_location": other_location,
            "reason": "Operational relocation",
        }
        values.update(overrides)
        return request_transfer(**values)

    return make_transfer
