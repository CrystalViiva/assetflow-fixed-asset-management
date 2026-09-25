from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections

from assets.models import AssetStatus
from audit.models import AuditLog
from depreciation.models import (
    AccountingPeriod,
    DepreciationEntry,
    PeriodStatus,
    ScheduleStatus,
)
from depreciation.services import (
    close_accounting_period,
    create_accounting_period,
    generate_depreciation_schedule,
    post_depreciation,
)


@pytest.mark.django_db
def test_period_identity_is_organization_scoped_and_unique(accountant, other_organization):
    period = create_accounting_period(actor=accountant, year=2025, month=2)
    assert period.first_day == date(2025, 2, 1)
    assert AccountingPeriod.objects.filter(organization=other_organization).count() == 0
    with pytest.raises(ValidationError, match="already exists"):
        create_accounting_period(actor=accountant, year=2025, month=2)


@pytest.mark.django_db
def test_schedule_generation_snapshots_capitalized_basis_and_available_date(
    accountant, asset_factory
):
    asset = asset_factory()
    schedule = generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    assert schedule.capitalized_cost == Decimal("12000000.00")
    assert schedule.depreciable_base == Decimal("10000000.00")
    assert schedule.periodic_depreciation == Decimal("166666.67")
    assert schedule.start_date == date(2025, 2, 15)
    assert schedule.end_date == date(2030, 1, 31)
    assert AuditLog.objects.filter(action="DEPRECIATION_SCHEDULE_CREATED").count() == 1
    with pytest.raises(ValidationError, match="already exists"):
        generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)


@pytest.mark.django_db
def test_posting_rolls_forward_and_audits_atomically(accountant, asset_factory):
    asset = asset_factory()
    schedule = generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    period = create_accounting_period(actor=accountant, year=2025, month=2)
    entry = post_depreciation(asset_id=asset.pk, period_id=period.pk, actor=accountant)
    asset.refresh_from_db()
    assert entry.opening_book_value == Decimal("12000000.00")
    assert entry.depreciation_amount == Decimal("166666.67")
    assert entry.closing_book_value == Decimal("11833333.33")
    assert asset.current_book_value == entry.closing_book_value
    assert asset.accumulated_depreciation == Decimal("166666.67")
    assert AuditLog.objects.filter(action="DEPRECIATION_POSTED", entity_id=str(entry.pk)).exists()
    with pytest.raises(ValidationError):
        post_depreciation(asset_id=asset.pk, period_id=period.pk, actor=accountant)
    asset.refresh_from_db()
    assert asset.accumulated_depreciation == Decimal("166666.67")
    assert schedule.status == ScheduleStatus.ACTIVE


@pytest.mark.django_db
def test_posting_rejects_gap_closed_period_and_unsupported_method(accountant, asset_factory):
    asset = asset_factory()
    generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    march = create_accounting_period(actor=accountant, year=2025, month=3)
    with pytest.raises(ValidationError, match="sequentially"):
        post_depreciation(asset_id=asset.pk, period_id=march.pk, actor=accountant)

    february = create_accounting_period(actor=accountant, year=2025, month=2)
    close_accounting_period(period_id=february.pk, actor=accountant)
    with pytest.raises(ValidationError, match="open period"):
        post_depreciation(asset_id=asset.pk, period_id=february.pk, actor=accountant)

    asset2 = asset_factory(asset_tag="AST-RBM", depreciation_method="RBM")
    with pytest.raises(ValidationError, match="not implemented"):
        generate_depreciation_schedule(asset_id=asset2.pk, actor=accountant)


@pytest.mark.django_db
def test_close_period_audits_and_cannot_close_twice(accountant):
    period = create_accounting_period(actor=accountant, year=2026, month=1)
    closed = close_accounting_period(period_id=period.pk, actor=accountant)
    assert closed.status == PeriodStatus.CLOSED
    assert closed.closed_by == accountant
    assert AuditLog.objects.filter(action="ACCOUNTING_PERIOD_CLOSED").count() == 1
    with pytest.raises(ValidationError, match="Only open"):
        close_accounting_period(period_id=period.pk, actor=accountant)


@pytest.mark.django_db
def test_audit_failure_rolls_back_entry_and_asset_balance(accountant, asset_factory):
    asset = asset_factory()
    generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    period = create_accounting_period(actor=accountant, year=2025, month=2)
    before = AuditLog.objects.count()
    with patch(
        "depreciation.services.posting.record_event",
        side_effect=RuntimeError("audit failure"),
    ):
        with pytest.raises(RuntimeError):
            post_depreciation(asset_id=asset.pk, period_id=period.pk, actor=accountant)
    asset.refresh_from_db()
    assert asset.current_book_value == Decimal("12000000.00")
    assert asset.accumulated_depreciation == Decimal("0.00")
    assert DepreciationEntry.objects.count() == 0
    assert AuditLog.objects.count() == before


@pytest.mark.django_db
def test_full_life_reaches_residual_exactly(accountant, asset_factory):
    asset = asset_factory(
        asset_tag="AST-ONE-MONTH",
        purchase_cost=Decimal("100.00"),
        residual_value=Decimal("10.00"),
        current_book_value=Decimal("100.00"),
        useful_life_months=1,
        acquisition_date="2024-12-15",
        capitalization_date="2025-01-01",
        available_for_use_date="2025-01-20",
    )
    schedule = generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    period = create_accounting_period(actor=accountant, year=2025, month=1)
    entry = post_depreciation(asset_id=asset.pk, period_id=period.pk, actor=accountant)
    asset.refresh_from_db()
    schedule.refresh_from_db()
    assert entry.depreciation_amount == Decimal("90.00")
    assert asset.current_book_value == Decimal("10.00")
    assert asset.accumulated_depreciation == Decimal("90.00")
    assert schedule.status == ScheduleStatus.COMPLETE


@pytest.mark.django_db
def test_uncapitalized_and_cross_organization_assets_are_rejected(
    accountant, asset_factory, other_organization
):
    from assets.models import Asset, AssetCategory

    draft = asset_factory(asset_tag="AST-DRAFT", status=AssetStatus.DRAFT)
    with pytest.raises(ValidationError, match="capitalized"):
        generate_depreciation_schedule(asset_id=draft.pk, actor=accountant)
    category = AssetCategory.objects.create(
        organization=other_organization, name="Other", code="OTHER", default_useful_life_months=12
    )
    foreign = Asset.objects.create(
        organization=other_organization,
        category=category,
        asset_tag="FOREIGN",
        name="Foreign asset",
        status=AssetStatus.ACTIVE,
        purchase_cost=Decimal("1.00"),
        current_book_value=Decimal("1.00"),
        useful_life_months=1,
        capitalization_date="2025-01-01",
        available_for_use_date="2025-01-01",
    )
    with pytest.raises(ValidationError, match="not found"):
        generate_depreciation_schedule(asset_id=foreign.pk, actor=accountant)


@pytest.mark.django_db
def test_sixty_month_schedule_finishes_at_residual(accountant, asset_factory):
    asset = asset_factory()
    generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    final = None
    for offset in range(60):
        absolute = 2025 * 12 + 1 + offset
        year, month_index = divmod(absolute, 12)
        period = create_accounting_period(actor=accountant, year=year, month=month_index + 1)
        final = post_depreciation(asset_id=asset.pk, period_id=period.pk, actor=accountant)
    asset.refresh_from_db()
    assert DepreciationEntry.objects.count() == 60
    assert asset.accumulated_depreciation == Decimal("10000000.00")
    assert asset.current_book_value == Decimal("2000000.00")
    assert final.depreciation_amount == Decimal("166666.47")


@pytest.mark.django_db
def test_zero_depreciable_amount_keeps_book_value_at_residual(accountant, asset_factory):
    asset = asset_factory(
        asset_tag="AST-ZERO-DEP",
        purchase_cost=Decimal("100.00"),
        residual_value=Decimal("100.00"),
        current_book_value=Decimal("100.00"),
        useful_life_months=1,
    )
    generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    period = create_accounting_period(actor=accountant, year=2025, month=2)
    entry = post_depreciation(asset_id=asset.pk, period_id=period.pk, actor=accountant)
    asset.refresh_from_db()
    assert entry.depreciation_amount == Decimal("0.00")
    assert asset.current_book_value == Decimal("100.00")
    assert asset.accumulated_depreciation == Decimal("0.00")


@pytest.mark.django_db(transaction=True)
def test_concurrent_posting_for_same_asset_period_commits_only_once(accountant, asset_factory):
    from accounts.models import User

    asset = asset_factory()
    generate_depreciation_schedule(asset_id=asset.pk, actor=accountant)
    period = create_accounting_period(actor=accountant, year=2025, month=2)
    barrier = Barrier(2)

    def attempt():
        close_old_connections()
        try:
            actor = User.objects.get(pk=accountant.pk)
            barrier.wait(timeout=10)
            try:
                post_depreciation(asset_id=asset.pk, period_id=period.pk, actor=actor)
                return "posted"
            except ValidationError:
                return "rejected"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result(timeout=30)
            for future in (executor.submit(attempt), executor.submit(attempt))
        ]
    assert sorted(results) == ["posted", "rejected"]
    assert DepreciationEntry.objects.filter(asset=asset, accounting_period=period).count() == 1
    asset.refresh_from_db()
    assert asset.accumulated_depreciation == Decimal("166666.67")
