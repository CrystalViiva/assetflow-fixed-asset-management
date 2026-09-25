from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from assets.models import Acquisition, AcquisitionStatus


@pytest.mark.django_db
def test_acquisition_creation_derives_decimal_capitalized_cost(acquisition_factory):
    acquisition = acquisition_factory()

    assert acquisition.total_cost == Decimal("11500000.00")
    assert acquisition.calculate_capitalized_cost() == Decimal("11500000.00")
    assert acquisition.status == AcquisitionStatus.DRAFT
    assert isinstance(acquisition.total_cost, Decimal)


@pytest.mark.django_db
def test_saving_only_a_cost_component_also_persists_the_derived_total(acquisition_factory):
    acquisition = acquisition_factory()
    acquisition.freight_cost = Decimal("750000.00")
    acquisition.save(update_fields=("freight_cost",))
    acquisition.refresh_from_db()

    assert acquisition.total_cost == Decimal("11750000.00")


@pytest.mark.django_db
def test_database_constraints_reject_negative_cost_and_forged_total(acquisition_factory):
    acquisition = acquisition_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        Acquisition.objects.filter(pk=acquisition.pk).update(freight_cost=Decimal("-1.00"))

    with pytest.raises(IntegrityError), transaction.atomic():
        Acquisition.objects.filter(pk=acquisition.pk).update(total_cost=Decimal("1.00"))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field",
    (
        "purchase_price",
        "freight_cost",
        "installation_cost",
        "civil_works_cost",
        "other_capitalizable_cost",
    ),
)
def test_negative_cost_components_are_rejected(asset_manager, asset_factory, field):
    values = {
        "organization": asset_manager.organization,
        "asset": asset_factory(f"AST-NEG-{field[:4]}"),
        "acquisition_date": date(2025, 1, 15),
        "purchase_price": Decimal("100.00"),
    }
    values[field] = Decimal("-1.00")
    acquisition = Acquisition(**values)

    with pytest.raises(ValidationError) as exc_info:
        acquisition.full_clean()

    assert field in exc_info.value.message_dict


@pytest.mark.django_db
def test_zero_capitalized_cost_is_rejected(asset_manager, asset_factory):
    acquisition = Acquisition(
        organization=asset_manager.organization,
        asset=asset_factory("AST-ZERO-COST"),
        acquisition_date=date(2025, 1, 15),
    )

    with pytest.raises(ValidationError) as exc_info:
        acquisition.full_clean()

    assert "total_cost" in exc_info.value.message_dict


@pytest.mark.django_db
def test_capitalization_date_cannot_precede_acquisition_date(acquisition_factory):
    acquisition = acquisition_factory()
    acquisition.capitalization_date = date(2025, 1, 14)

    with pytest.raises(ValidationError) as exc_info:
        acquisition.full_clean()

    assert "capitalization_date" in exc_info.value.message_dict


@pytest.mark.django_db
def test_acquisition_rejects_cross_organization_asset(
    organization, other_organization, other_category, asset_manager
):
    from assets.models import Asset

    other_asset = Asset.objects.create(
        organization=other_organization,
        category=other_category,
        asset_tag="AST-FOREIGN-ACQ",
        name="Foreign asset",
    )
    acquisition = Acquisition(
        organization=organization,
        asset=other_asset,
        acquisition_date=date(2025, 1, 15),
        purchase_price=Decimal("1.00"),
    )

    with pytest.raises(ValidationError) as exc_info:
        acquisition.full_clean()

    assert "asset" in exc_info.value.message_dict


@pytest.mark.django_db
def test_acquisition_asset_relationship_is_unique(acquisition_factory, asset_factory):
    acquisition = acquisition_factory()
    duplicate = Acquisition(
        organization=acquisition.organization,
        asset=acquisition.asset,
        acquisition_date=date(2025, 1, 15),
        purchase_price=Decimal("1.00"),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        duplicate.save()


@pytest.mark.django_db
def test_acquisition_currency_must_be_supported_and_match_organization(
    acquisition_factory, organization
):
    acquisition = acquisition_factory()
    acquisition.currency = "XXX"
    with pytest.raises(ValidationError) as unsupported:
        acquisition.full_clean()
    assert "currency" in unsupported.value.message_dict

    organization.currency = "USD"
    organization.save(update_fields=("currency",))
    acquisition = acquisition_factory(currency="NGN", asset_tag="AST-CURRENCY-MISMATCH")
    with pytest.raises(ValidationError) as mismatch:
        acquisition.full_clean()
    assert "currency" in mismatch.value.message_dict
