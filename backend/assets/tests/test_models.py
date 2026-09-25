from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from assets.models import Asset, AssetCategory, AssetStatus, DepreciationMethod


@pytest.mark.django_db
def test_valid_asset_creation_uses_master_data_defaults(
    asset_manager, category, department, location
):
    asset = Asset(
        organization=asset_manager.organization,
        category=category,
        department=department,
        location=location,
        asset_tag="AST-100001",
        name="Finance laptop",
        created_by=asset_manager,
        updated_by=asset_manager,
    )
    asset.full_clean()
    asset.save()

    assert asset.pk is not None
    assert asset.status == AssetStatus.DRAFT
    assert asset.purchase_cost == Decimal("0.00")
    assert asset.residual_value == Decimal("0.00")
    assert asset.useful_life_months is None
    assert asset.current_book_value == Decimal("0.00")
    assert asset.accumulated_depreciation == Decimal("0.00")


@pytest.mark.django_db
def test_category_defaults_are_decimal_and_method_choices_are_explicit(category):
    assert category.capitalization_threshold == Decimal("50000.00")
    assert category.default_depreciation_method == DepreciationMethod.SLM
    assert set(DepreciationMethod.values) == {"SLM", "RBM", "UOP", "SYD"}


@pytest.mark.django_db
def test_category_code_and_name_are_unique_within_organization(
    organization, other_organization, category
):
    AssetCategory.objects.create(
        organization=other_organization,
        name=category.name,
        code=category.code,
        default_useful_life_months=24,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        AssetCategory.objects.create(
            organization=organization,
            name="Other category",
            code=category.code,
            default_useful_life_months=24,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        AssetCategory.objects.create(
            organization=organization,
            name=category.name,
            code="OTHER",
            default_useful_life_months=24,
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"asset_tag": "   "}, "asset_tag"),
        ({"purchase_cost": Decimal("-1.00")}, "purchase_cost"),
        ({"residual_value": Decimal("-1.00")}, "residual_value"),
        (
            {"purchase_cost": Decimal("100.00"), "residual_value": Decimal("101.00")},
            "residual_value",
        ),
        ({"useful_life_months": 0}, "useful_life_months"),
        (
            {"capitalization_date": date(2024, 1, 1), "acquisition_date": date(2024, 2, 1)},
            "capitalization_date",
        ),
        ({"current_book_value": Decimal("-0.01")}, "current_book_value"),
        ({"accumulated_depreciation": Decimal("-0.01")}, "accumulated_depreciation"),
    ],
)
def test_asset_accounting_and_identification_validation(asset_instance_factory, overrides, field):
    asset = asset_instance_factory(**{"asset_tag": "AST-VALIDATION", **overrides})

    with pytest.raises(ValidationError) as exc_info:
        asset.full_clean()

    assert field in exc_info.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"default_useful_life_months": 0}, "default_useful_life_months"),
        ({"capitalization_threshold": Decimal("-1.00")}, "capitalization_threshold"),
    ],
)
def test_category_policy_validation(organization, overrides, field):
    values = {
        "organization": organization,
        "name": "Test Category",
        "code": "TEST",
        "default_useful_life_months": 12,
    }
    values.update(overrides)
    category = AssetCategory(**values)

    with pytest.raises(ValidationError) as exc_info:
        category.full_clean()

    assert field in exc_info.value.message_dict


@pytest.mark.django_db
def test_asset_tag_uniqueness_is_scoped_to_organization(
    asset_factory, other_organization, other_category
):
    asset_factory("AST-SHARED")
    Asset.objects.create(
        organization=other_organization,
        category=other_category,
        asset_tag="AST-SHARED",
        name="Same tag in another organization",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        asset_factory("AST-SHARED")
