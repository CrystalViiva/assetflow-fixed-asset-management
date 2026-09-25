from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.utils import timezone

from assets.models import AssetStatus
from audit.models import AuditLog
from depreciation.models import AccountingPeriod
from disposals.models import Disposal, DisposalStatus
from disposals.services import (
    approve_disposal,
    cancel_disposal,
    complete_disposal,
    create_disposal,
    reject_disposal,
    submit_disposal,
)
from maintenance.models import WorkOrder


@pytest.mark.django_db
def test_create_validate_submit_approve_and_self_approval_is_rejected(
    disposal_factory, asset_manager, approver
):
    disposal = disposal_factory()
    assert disposal.status == DisposalStatus.DRAFT
    assert disposal.proceeds == Decimal("6000.00")
    submitted = submit_disposal(disposal_id=disposal.pk, actor=asset_manager)
    assert submitted.status == DisposalStatus.PENDING_APPROVAL
    with pytest.raises(ValidationError, match="own disposal"):
        approve_disposal(disposal_id=disposal.pk, actor=asset_manager)
    approved = approve_disposal(disposal_id=disposal.pk, actor=approver)
    assert approved.status == DisposalStatus.APPROVED
    assert approved.approved_by == approver
    assert AuditLog.objects.filter(action="DISPOSAL_CREATED").exists()
    assert AuditLog.objects.filter(action="DISPOSAL_SUBMITTED").exists()
    assert AuditLog.objects.filter(action="DISPOSAL_APPROVED").exists()


@pytest.mark.django_db
def test_negative_proceeds_invalid_method_cross_org_and_active_uniqueness(
    asset_factory, asset_manager, other_organization, disposal_factory
):
    asset = asset_factory()
    with pytest.raises(ValidationError):
        create_disposal(
            actor=asset_manager,
            asset_id=asset.pk,
            disposal_date="2026-01-01",
            disposal_method="SALE",
            reason="Bad amount",
            proceeds="-0.01",
        )
    with pytest.raises(ValidationError):
        create_disposal(
            actor=asset_manager,
            asset_id=asset.pk,
            disposal_date="2026-01-01",
            disposal_method="UNKNOWN",
            reason="Bad method",
            proceeds="0",
        )
    foreign_category = asset.category.__class__.objects.create(
        organization=other_organization,
        name="Foreign category",
        code="FOREIGN",
        default_useful_life_months=12,
    )
    from assets.models import Asset

    foreign_asset = Asset.objects.create(
        organization=other_organization,
        category=foreign_category,
        asset_tag="FOREIGN-1",
        name="Foreign asset",
        status="ACTIVE",
        capitalization_date="2020-01-01",
        purchase_cost="100.00",
        current_book_value="100.00",
    )
    with pytest.raises(ValidationError, match="not found"):
        create_disposal(
            actor=asset_manager,
            asset_id=foreign_asset.pk,
            disposal_date="2026-01-01",
            disposal_method="SALE",
            reason="Cross tenant",
            proceeds="1.00",
        )

    disposal = disposal_factory(asset=asset)
    with pytest.raises((ValidationError, IntegrityError)):
        disposal_factory(asset=asset)
    with pytest.raises(IntegrityError), transaction.atomic():
        Disposal.objects.create(
            organization=asset.organization,
            asset=asset,
            disposal_date="2026-01-01",
            disposal_method="SALE",
            reason="Duplicate",
            proceeds="0.00",
            currency="NGN",
            requested_by=asset_manager,
            created_by=asset_manager,
            updated_by=asset_manager,
        )
    assert Disposal.objects.filter(pk=disposal.pk).exists()


@pytest.mark.django_db
def test_reject_and_cancel_are_terminal_and_leave_asset_active(
    disposal_factory, asset_manager, approver, asset_factory
):
    from disposals.services import submit_disposal

    rejected = disposal_factory()
    submit_disposal(disposal_id=rejected.pk, actor=asset_manager)
    reject_disposal(disposal_id=rejected.pk, actor=approver, reason="Insufficient evidence")
    assert Disposal.objects.get(pk=rejected.pk).status == DisposalStatus.REJECTED
    with pytest.raises(ValidationError):
        approve_disposal(disposal_id=rejected.pk, actor=approver)

    cancelled = disposal_factory(asset=asset_factory())
    cancel_disposal(disposal_id=cancelled.pk, actor=asset_manager, reason="Withdrawn")
    assert Disposal.objects.get(pk=cancelled.pk).status == DisposalStatus.CANCELLED
    assert cancelled.asset.status == AssetStatus.ACTIVE
    assert AuditLog.objects.filter(action="DISPOSAL_REJECTED").exists()
    assert AuditLog.objects.filter(action="DISPOSAL_CANCELLED").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "capitalized_cost",
        "accumulated",
        "book_value",
        "residual",
        "proceeds",
        "expected_carrying",
        "expected_gain",
    ),
    [
        ("12000.00", "7000.00", "5000.00", "2000.00", "6000.00", "5000.00", "1000.00"),
        ("12000.00", "7000.00", "5000.00", "2000.00", "4000.00", "5000.00", "-1000.00"),
        ("12000.00", "10000.00", "2000.00", "2000.00", "0.00", "2000.00", "-2000.00"),
    ],
)
def test_completion_snapshots_carrying_amount_gain_loss_and_disposes_asset(
    asset_factory,
    asset_manager,
    approved_disposal,
    capitalized_cost,
    accumulated,
    book_value,
    residual,
    proceeds,
    expected_carrying,
    expected_gain,
):
    asset = approved_disposal.asset
    asset.purchase_cost = Decimal(capitalized_cost)
    asset.accumulated_depreciation = Decimal(accumulated)
    asset.current_book_value = Decimal(book_value)
    asset.residual_value = Decimal(residual)
    asset.save(
        update_fields=(
            "purchase_cost",
            "accumulated_depreciation",
            "current_book_value",
            "residual_value",
        )
    )
    approved_disposal.proceeds = Decimal(proceeds)
    approved_disposal.save(update_fields=("proceeds",))

    completed = complete_disposal(disposal_id=approved_disposal.pk, actor=asset_manager)
    asset.refresh_from_db()
    completed.refresh_from_db()
    assert asset.status == AssetStatus.DISPOSED
    assert completed.status == DisposalStatus.COMPLETED
    assert completed.capitalized_cost_at_disposal == Decimal(capitalized_cost)
    assert completed.accumulated_depreciation_at_disposal == Decimal(accumulated)
    assert completed.carrying_amount == Decimal(expected_carrying)
    assert completed.gain_or_loss == Decimal(expected_gain)
    assert completed.proceeds == Decimal(proceeds)
    assert AuditLog.objects.filter(action="ASSET_DERECOGNIZED", entity_id=str(asset.pk)).exists()
    assert AuditLog.objects.filter(
        action="DISPOSAL_COMPLETED", entity_id=str(completed.pk)
    ).exists()
    with pytest.raises(ValidationError, match="immutable"):
        completed.reason = "Rewrite history"
        completed.save()
    with pytest.raises(ValidationError):
        complete_disposal(disposal_id=completed.pk, actor=asset_manager)


@pytest.mark.django_db
def test_disposal_completion_audit_failure_rolls_back_snapshot_and_asset(
    approved_disposal, asset_manager
):
    asset = approved_disposal.asset
    with patch("disposals.services.record_event", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError):
            complete_disposal(disposal_id=approved_disposal.pk, actor=asset_manager)
    approved_disposal.refresh_from_db()
    asset.refresh_from_db()
    assert approved_disposal.status == DisposalStatus.APPROVED
    assert approved_disposal.carrying_amount is None
    assert asset.status == AssetStatus.ACTIVE


@pytest.mark.django_db
def test_open_assignment_transfer_and_work_order_block_derecognition(
    disposal_factory, asset_manager, approver, employee, department, other_department, location
):
    from maintenance.services import assign_work_order, create_work_order
    from transfers.services import assign_asset, request_transfer

    cases = ("assignment", "transfer", "work_order")
    for kind in cases:
        disposal = disposal_factory()
        asset = disposal.asset
        submit_disposal(disposal_id=disposal.pk, actor=asset_manager)
        approve_disposal(disposal_id=disposal.pk, actor=approver)
        if kind == "assignment":
            assign_asset(asset_id=asset.pk, actor=asset_manager, assigned_to=employee)
        elif kind == "transfer":
            request_transfer(
                asset_id=asset.pk,
                actor=asset_manager,
                to_department=other_department,
                to_location=location,
                reason="Pending transfer",
            )
        else:
            order = create_work_order(
                actor=asset_manager,
                asset_id=asset.pk,
                maintenance_type="CORRECTIVE",
                description="Open repair",
            )
            assign_work_order(work_order_id=order.pk, assigned_to=employee, actor=asset_manager)
        with pytest.raises(ValidationError, match="assignment|transfer|work orders"):
            complete_disposal(disposal_id=disposal.pk, actor=asset_manager)
        assert Disposal.objects.get(pk=disposal.pk).status == DisposalStatus.APPROVED


@pytest.mark.django_db
def test_disposed_asset_is_blocked_from_future_depreciation_assignment_transfer_and_work_order(
    approved_disposal, asset_manager, location, other_department
):
    from depreciation.services.posting import post_depreciation
    from maintenance.services import create_work_order
    from transfers.services import assign_asset, request_transfer

    disposal = complete_disposal(disposal_id=approved_disposal.pk, actor=asset_manager)
    asset = disposal.asset
    period = AccountingPeriod.objects.create(organization=asset.organization, year=2026, month=9)
    with pytest.raises(ValidationError, match="active assets"):
        post_depreciation(asset_id=asset.pk, period_id=period.pk, actor=asset_manager)
    with pytest.raises(ValidationError, match="lifecycle"):
        assign_asset(asset_id=asset.pk, actor=asset_manager)
    with pytest.raises(ValidationError, match="lifecycle"):
        request_transfer(
            asset_id=asset.pk,
            actor=asset_manager,
            to_department=other_department,
            to_location=location,
            reason="Too late",
        )
    with pytest.raises(ValidationError, match="lifecycle"):
        create_work_order(
            actor=asset_manager,
            asset_id=asset.pk,
            maintenance_type="CORRECTIVE",
            description="Too late",
        )


@pytest.mark.django_db
def test_derecognition_preserves_depreciation_and_completed_operational_history(
    asset_factory, asset_manager, approver, employee, other_department, location
):
    from depreciation.models import DepreciationEntry
    from depreciation.services.posting import (
        create_accounting_period,
        generate_depreciation_schedule,
        post_depreciation,
    )
    from maintenance.models import MaintenanceRecord
    from maintenance.services import complete_work_order, create_work_order, start_work_order
    from transfers.services import (
        approve_transfer,
        assign_asset,
        complete_transfer,
        request_transfer,
        return_asset,
    )

    asset = asset_factory(
        accumulated_depreciation=Decimal("0.00"), current_book_value=Decimal("12000.00")
    )
    generate_depreciation_schedule(asset_id=asset.pk, actor=asset_manager)
    period = create_accounting_period(actor=asset_manager, year=2020, month=1)
    entry = post_depreciation(asset_id=asset.pk, period_id=period.pk, actor=asset_manager)

    assignment = assign_asset(asset_id=asset.pk, actor=asset_manager, assigned_to=employee)
    return_asset(asset_id=asset.pk, actor=asset_manager, assignment_id=assignment.pk)
    transfer = request_transfer(
        asset_id=asset.pk,
        actor=asset_manager,
        to_department=other_department,
        to_location=location,
        reason="Move before retirement",
    )
    approve_transfer(transfer_id=transfer.pk, actor=approver)
    complete_transfer(transfer_id=transfer.pk, actor=approver)
    work_order = create_work_order(
        actor=asset_manager,
        asset_id=asset.pk,
        maintenance_type="INSPECTION",
        description="Final inspection",
    )
    start_work_order(work_order_id=work_order.pk, actor=asset_manager)
    _, maintenance_record = complete_work_order(
        work_order_id=work_order.pk, actor=asset_manager, resolution="Inspection complete"
    )

    disposal = create_disposal(
        actor=asset_manager,
        asset_id=asset.pk,
        disposal_date=timezone.localdate(),
        disposal_method="SALE",
        reason="Retired after service",
        proceeds="0.00",
    )
    submit_disposal(disposal_id=disposal.pk, actor=asset_manager)
    approve_disposal(disposal_id=disposal.pk, actor=approver)
    complete_disposal(disposal_id=disposal.pk, actor=asset_manager)

    assert DepreciationEntry.objects.filter(pk=entry.pk).exists()
    assignment.refresh_from_db()
    assert assignment.returned_at is not None
    assert type(transfer).objects.filter(pk=transfer.pk, status="COMPLETED").exists()
    assert WorkOrder.objects.filter(pk=work_order.pk, status="COMPLETED").exists()
    assert MaintenanceRecord.objects.filter(pk=maintenance_record.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_completion_derecognizes_once(approved_disposal, asset_manager):
    from accounts.models import User

    disposal_id = approved_disposal.pk
    asset_id = approved_disposal.asset_id
    barrier = Barrier(2)

    def finish():
        close_old_connections()
        try:
            actor = User.objects.get(pk=asset_manager.pk)
            barrier.wait(timeout=10)
            try:
                complete_disposal(disposal_id=disposal_id, actor=actor)
                return "completed"
            except ValidationError:
                return "rejected"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result(timeout=30)
            for future in (executor.submit(finish), executor.submit(finish))
        ]
    assert sorted(results) == ["completed", "rejected"]
    assert Disposal.objects.filter(pk=disposal_id, status=DisposalStatus.COMPLETED).count() == 1
    assert Disposal.objects.filter(asset_id=asset_id, status=DisposalStatus.COMPLETED).count() == 1
    assert (
        AuditLog.objects.filter(action="DISPOSAL_COMPLETED", entity_id=str(disposal_id)).count()
        == 1
    )
