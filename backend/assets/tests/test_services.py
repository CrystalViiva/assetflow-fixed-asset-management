from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from assets.models import AssetStatus, DepreciationMethod
from assets.services import create_asset, update_asset
from audit.models import AuditLog


@pytest.mark.django_db
def test_create_asset_applies_category_defaults_and_writes_audit(
    asset_manager, category, department, location
):
    asset = create_asset(
        actor=asset_manager,
        data={
            "asset_tag": "AST-SERVICE-01",
            "name": "Operations laptop",
            "category": category,
            "department": department,
            "location": location,
            "purchase_cost": Decimal("1200000.00"),
        },
        ip_address="192.0.2.15",
    )

    assert asset.organization == asset_manager.organization
    assert asset.useful_life_months == category.default_useful_life_months
    assert asset.depreciation_method == DepreciationMethod.SLM
    assert asset.status == AssetStatus.DRAFT
    event = AuditLog.objects.get(entity_type="ASSET", entity_id=str(asset.pk))
    assert event.organization == asset_manager.organization
    assert event.user == asset_manager
    assert event.action == "ASSET_CREATED"
    assert event.ip_address == "192.0.2.15"
    assert event.changes["asset_tag"]["to"] == "AST-SERVICE-01"


@pytest.mark.django_db
def test_explicit_asset_policy_overrides_category_defaults(asset_manager, category):
    asset = create_asset(
        actor=asset_manager,
        data={
            "asset_tag": "AST-SERVICE-02",
            "name": "Policy override laptop",
            "category": category,
            "useful_life_months": 60,
            "depreciation_method": DepreciationMethod.RBM,
        },
    )

    assert asset.useful_life_months == 60
    assert asset.depreciation_method == DepreciationMethod.RBM


@pytest.mark.django_db
def test_update_asset_writes_before_after_audit_information(asset_factory, asset_manager):
    asset = asset_factory("AST-UPDATE", manufacturer="Old manufacturer")

    updated_asset = update_asset(
        asset_id=asset.pk,
        actor=asset_manager,
        data={"manufacturer": "New manufacturer", "name": "Updated device"},
    )

    assert updated_asset.manufacturer == "New manufacturer"
    assert updated_asset.name == "Updated device"
    event = AuditLog.objects.get(action="ASSET_UPDATED", entity_id=str(asset.pk))
    assert event.changes == {
        "manufacturer": {"from": "Old manufacturer", "to": "New manufacturer"},
        "name": {"from": f"Asset {asset.asset_tag}", "to": "Updated device"},
    }
    assert updated_asset.updated_by == asset_manager


@pytest.mark.django_db
def test_noop_update_does_not_create_an_audit_event(asset_factory, asset_manager):
    asset = asset_factory("AST-NOOP", manufacturer="Acme")
    before_count = AuditLog.objects.count()

    update_asset(asset_id=asset.pk, actor=asset_manager, data={"manufacturer": "Acme"})

    assert AuditLog.objects.count() == before_count


@pytest.mark.django_db
@pytest.mark.parametrize(
    "foreign_field,foreign_fixture",
    [
        ("category", "other_category"),
        ("department", "other_department"),
        ("location", "other_location"),
    ],
)
def test_service_rejects_related_records_from_another_organization(
    request, asset_manager, category, foreign_field, foreign_fixture
):
    related_object = request.getfixturevalue(foreign_fixture)
    data = {
        "asset_tag": "AST-CROSS-ORG",
        "name": "Cross organization attempt",
        "category": category,
    }
    data[foreign_field] = related_object

    with pytest.raises(ValidationError) as exc_info:
        create_asset(actor=asset_manager, data=data)

    assert foreign_field in exc_info.value.message_dict
    assert not AuditLog.objects.filter(action="ASSET_CREATED").exists()


@pytest.mark.django_db
def test_service_rejects_mutation_of_lifecycle_and_ledger_fields(asset_manager, category):
    with pytest.raises(ValidationError) as exc_info:
        create_asset(
            actor=asset_manager,
            data={
                "asset_tag": "AST-STATUS",
                "name": "Status injection attempt",
                "category": category,
                "status": AssetStatus.ACTIVE,
            },
        )

    assert "status" in exc_info.value.message_dict
