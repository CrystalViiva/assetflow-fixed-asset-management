from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections

from accounts.models import User
from assets.models import AcquisitionStatus, AssetStatus
from assets.services.acquisition import (
    calculate_capitalized_cost,
    capitalize_acquisition,
    create_acquisition,
    update_acquisition,
)
from audit.models import AuditLog
from audit.services import record_event as persist_audit_event


def acquisition_data(asset, **overrides):
    values = {
        "asset": asset,
        "vendor_name": "Lagos Industrial Supplies Ltd",
        "invoice_number": "INV-2025-0001",
        "reference": "PO-2025-0110",
        "acquisition_date": date(2025, 1, 15),
        "capitalization_date": date(2025, 2, 1),
        "purchase_price": Decimal("10000000.00"),
        "freight_cost": Decimal("500000.00"),
        "installation_cost": Decimal("1000000.00"),
        "civil_works_cost": Decimal("0.00"),
        "other_capitalizable_cost": Decimal("0.00"),
    }
    values.update(overrides)
    return values


@pytest.mark.django_db
def test_calculate_capitalized_cost_uses_decimal_sum():
    assert calculate_capitalized_cost(
        purchase_price=Decimal("10000000.00"),
        freight_cost=Decimal("500000.00"),
        installation_cost=Decimal("1000000.00"),
        civil_works_cost=Decimal("0.00"),
        other_capitalizable_cost=Decimal("0.00"),
    ) == Decimal("11500000.00")


@pytest.mark.django_db
def test_create_acquisition_uses_organization_currency_and_audits(asset_manager, asset_factory):
    asset = asset_factory("AST-ACQ-CREATE")
    acquisition = create_acquisition(
        actor=asset_manager,
        data=acquisition_data(asset),
        ip_address="192.0.2.5",
    )

    assert acquisition.currency == "NGN"
    assert acquisition.total_cost == Decimal("11500000.00")
    event = AuditLog.objects.get(action="ACQUISITION_CREATED")
    assert event.entity_type == "ACQUISITION"
    assert event.entity_id == str(acquisition.pk)
    assert event.user == asset_manager
    assert event.organization == asset_manager.organization
    assert event.ip_address == "192.0.2.5"


@pytest.mark.django_db
def test_update_acquisition_recalculates_total_and_audits_material_change(
    asset_manager, asset_factory
):
    asset = asset_factory("AST-ACQ-UPDATE")
    acquisition = create_acquisition(actor=asset_manager, data=acquisition_data(asset))

    updated = update_acquisition(
        acquisition_id=acquisition.pk,
        actor=asset_manager,
        data={"freight_cost": Decimal("750000.00")},
    )

    assert updated.total_cost == Decimal("11750000.00")
    event = AuditLog.objects.get(action="ACQUISITION_UPDATED")
    assert event.changes["freight_cost"] == {"from": "500000.00", "to": "750000.00"}
    assert event.changes["total_cost"] == {"from": "11500000.00", "to": "11750000.00"}


@pytest.mark.django_db
def test_capitalization_updates_asset_and_acquisition_once_with_audit(
    asset_manager, asset_factory, category
):
    asset = asset_factory(
        "AST-CAP-SUCCESS",
        purchase_cost=Decimal("250000.00"),
        residual_value=Decimal("250000.00"),
    )
    acquisition = create_acquisition(
        actor=asset_manager,
        data=acquisition_data(asset),
    )

    capitalized = capitalize_acquisition(
        acquisition_id=acquisition.pk,
        actor=asset_manager,
        ip_address="192.0.2.8",
    )
    asset.refresh_from_db()
    capitalized.refresh_from_db()

    assert asset.status == AssetStatus.ACTIVE
    assert asset.purchase_cost == Decimal("11500000.00")
    assert asset.current_book_value == Decimal("11500000.00")
    assert asset.accumulated_depreciation == Decimal("0.00")
    assert asset.acquisition_date == date(2025, 1, 15)
    assert asset.capitalization_date == date(2025, 2, 1)
    assert asset.useful_life_months == category.default_useful_life_months
    assert asset.updated_by == asset_manager
    assert capitalized.status == AcquisitionStatus.CAPITALIZED

    asset_event = AuditLog.objects.get(action="ASSET_CAPITALIZED")
    acquisition_event = AuditLog.objects.get(action="ACQUISITION_CAPITALIZED")
    assert asset_event.entity_id == str(asset.pk)
    assert asset_event.metadata["acquisition_id"] == str(acquisition.pk)
    assert asset_event.changes["purchase_cost"]["to"] == "11500000.00"
    assert acquisition_event.entity_id == str(acquisition.pk)
    assert acquisition_event.user == asset_manager
    assert acquisition_event.changes["capitalized_cost"] == {
        "from": None,
        "to": "11500000.00",
    }


@pytest.mark.django_db
def test_second_capitalization_is_rejected_without_duplicate_events(asset_manager, asset_factory):
    acquisition = create_acquisition(
        actor=asset_manager,
        data=acquisition_data(asset_factory("AST-CAP-ONCE")),
    )
    capitalize_acquisition(acquisition_id=acquisition.pk, actor=asset_manager)
    event_count = AuditLog.objects.count()

    with pytest.raises(ValidationError) as exc_info:
        capitalize_acquisition(acquisition_id=acquisition.pk, actor=asset_manager)

    assert "status" in exc_info.value.message_dict
    assert AuditLog.objects.count() == event_count


@pytest.mark.django_db(transaction=True)
def test_concurrent_capitalization_requests_only_commit_once(asset_manager, asset_factory):
    acquisition = create_acquisition(
        actor=asset_manager,
        data=acquisition_data(asset_factory("AST-CAP-CONCURRENT")),
    )
    barrier = Barrier(2)

    def attempt_capitalization():
        close_old_connections()
        try:
            actor = User.objects.get(pk=asset_manager.pk)
            barrier.wait(timeout=10)
            try:
                capitalize_acquisition(acquisition_id=acquisition.pk, actor=actor)
                return "capitalized"
            except ValidationError:
                return "rejected"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt_capitalization) for _ in range(2)]
        outcomes = [future.result(timeout=30) for future in futures]

    assert sorted(outcomes) == ["capitalized", "rejected"]
    assert AuditLog.objects.filter(action="ASSET_CAPITALIZED").count() == 1
    assert AuditLog.objects.filter(action="ACQUISITION_CAPITALIZED").count() == 1


@pytest.mark.django_db
def test_capitalization_rejects_missing_date_and_residual_above_cost(asset_manager, asset_factory):
    no_date = create_acquisition(
        actor=asset_manager,
        data=acquisition_data(asset_factory("AST-CAP-NO-DATE"), capitalization_date=None),
    )
    with pytest.raises(ValidationError) as missing_date:
        capitalize_acquisition(acquisition_id=no_date.pk, actor=asset_manager)
    assert "capitalization_date" in missing_date.value.message_dict

    high_residual = create_acquisition(
        actor=asset_manager,
        data=acquisition_data(
            asset_factory(
                "AST-CAP-HIGH-RESIDUAL",
                purchase_cost=Decimal("20.00"),
                residual_value=Decimal("20.00"),
            ),
            purchase_price=Decimal("10.00"),
            freight_cost=Decimal("0.00"),
            installation_cost=Decimal("0.00"),
        ),
    )
    high_residual.asset.residual_value = Decimal("20.00")
    high_residual.asset.save(update_fields=("residual_value",))

    with pytest.raises(ValidationError) as residual_error:
        capitalize_acquisition(acquisition_id=high_residual.pk, actor=asset_manager)
    assert "residual_value" in residual_error.value.message_dict
    high_residual.asset.refresh_from_db()
    assert high_residual.asset.status == AssetStatus.DRAFT


@pytest.mark.django_db
def test_capitalization_failure_rolls_back_asset_state_and_audit(asset_manager, asset_factory):
    asset = asset_factory("AST-CAP-ROLLBACK")
    acquisition = create_acquisition(actor=asset_manager, data=acquisition_data(asset))
    event_count = AuditLog.objects.count()

    def fail_after_asset_event(**event_data):
        if event_data["action"] == "ACQUISITION_CAPITALIZED":
            raise RuntimeError("audit down")
        return persist_audit_event(**event_data)

    with patch("assets.services.acquisition.record_event", side_effect=fail_after_asset_event):
        with pytest.raises(RuntimeError):
            capitalize_acquisition(acquisition_id=acquisition.pk, actor=asset_manager)

    asset.refresh_from_db()
    acquisition.refresh_from_db()
    assert asset.status == AssetStatus.DRAFT
    assert asset.purchase_cost == Decimal("0.00")
    assert asset.current_book_value == Decimal("0.00")
    assert acquisition.status == AcquisitionStatus.DRAFT
    assert AuditLog.objects.count() == event_count


@pytest.mark.django_db
def test_acquisition_cannot_be_created_for_another_organization(
    asset_manager, other_organization, other_category
):
    from assets.models import Asset

    other_asset = Asset.objects.create(
        organization=other_organization,
        category=other_category,
        asset_tag="AST-OTHER-ACQ-SVC",
        name="Other company asset",
    )

    with pytest.raises(ValidationError) as exc_info:
        create_acquisition(
            actor=asset_manager,
            data=acquisition_data(other_asset),
        )

    assert "asset" in exc_info.value.message_dict
    assert not AuditLog.objects.filter(action="ACQUISITION_CREATED").exists()
