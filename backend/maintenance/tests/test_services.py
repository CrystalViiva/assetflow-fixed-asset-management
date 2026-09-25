from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.utils import timezone

from assets.models import AssetStatus
from audit.models import AuditLog
from maintenance.models import MaintenancePlan, MaintenanceRecord, WorkOrder, WorkOrderStatus
from maintenance.services import (
    assign_work_order,
    cancel_work_order,
    complete_work_order,
    create_maintenance_cost,
    create_maintenance_plan,
    start_work_order,
)


@pytest.mark.django_db
def test_plan_creation_validation_and_inactivation_preserves_history(
    asset_factory, asset_manager, other_organization
):
    asset = asset_factory()
    plan = create_maintenance_plan(
        actor=asset_manager,
        asset_id=asset.pk,
        maintenance_type="PREVENTIVE",
        frequency_value=6,
        frequency_unit="MONTHS",
        next_due_date="2026-10-01",
    )
    assert plan.active is True
    plan.active = False
    plan.save()
    assert MaintenancePlan.objects.get(pk=plan.pk).active is False
    with pytest.raises(ValidationError, match="positive"):
        create_maintenance_plan(
            actor=asset_manager,
            asset_id=asset.pk,
            maintenance_type="INSPECTION",
            frequency_value=0,
            frequency_unit="DAYS",
            next_due_date="2026-10-01",
        )
    from assets.models import Asset, AssetCategory

    other_category = AssetCategory.objects.create(
        organization=other_organization,
        name="Other equipment",
        code="OTHER",
        default_useful_life_months=12,
    )
    foreign_asset = Asset.objects.create(
        organization=other_organization,
        category=other_category,
        asset_tag="FOREIGN-MNT",
        name="Foreign asset",
        status="ACTIVE",
    )
    with pytest.raises(ValidationError, match="not found"):
        create_maintenance_plan(
            actor=asset_manager,
            asset_id=foreign_asset.pk,
            maintenance_type="INSPECTION",
            frequency_value=1,
            frequency_unit="DAYS",
            next_due_date="2026-10-01",
        )
    with pytest.raises(ValidationError, match="deactivate"):
        plan.delete()


@pytest.mark.django_db
def test_disposed_assets_cannot_receive_plans_or_work_orders(asset_factory, asset_manager):
    asset = asset_factory(status=AssetStatus.DISPOSED)
    with pytest.raises(ValidationError, match="Disposed assets"):
        create_maintenance_plan(
            actor=asset_manager,
            asset_id=asset.pk,
            maintenance_type="PREVENTIVE",
            frequency_value=1,
            frequency_unit="MONTHS",
            next_due_date="2026-10-01",
        )
    from maintenance.services import create_work_order

    with pytest.raises(ValidationError, match="lifecycle"):
        create_work_order(
            actor=asset_manager,
            asset_id=asset.pk,
            maintenance_type="CORRECTIVE",
            description="Repair",
        )


@pytest.mark.django_db
def test_work_order_number_and_complete_cost_record_lifecycle(
    asset_factory, asset_manager, employee, work_order_factory
):
    asset = asset_factory()
    first = work_order_factory(asset)
    second = work_order_factory(asset_factory())
    assert first.work_order_number == "WO-000001"
    assert second.work_order_number == "WO-000002"

    assigned = assign_work_order(work_order_id=first.pk, assigned_to=employee, actor=asset_manager)
    assert assigned.status == WorkOrderStatus.ASSIGNED
    started = start_work_order(work_order_id=first.pk, actor=asset_manager)
    asset.refresh_from_db()
    assert started.status == WorkOrderStatus.IN_PROGRESS
    assert started.started_at is not None
    assert asset.status == AssetStatus.IN_MAINTENANCE

    cost = create_maintenance_cost(
        actor=asset_manager,
        work_order_id=first.pk,
        cost_type="PARTS",
        description="Replacement belt",
        quantity="1.500",
        unit_cost="200.00",
    )
    assert str(cost.total_cost) == "300.00"
    fractional_cost = create_maintenance_cost(
        actor=asset_manager,
        work_order_id=first.pk,
        cost_type="OTHER",
        description="Fractional consumable",
        quantity="0.001",
        unit_cost="0.01",
    )
    assert str(fractional_cost.total_cost) == "0.00"
    completed, record = complete_work_order(
        work_order_id=first.pk,
        actor=asset_manager,
        resolution="Belt replaced",
        downtime_minutes=45,
        performed_by=employee,
    )
    asset.refresh_from_db()
    assert completed.status == WorkOrderStatus.COMPLETED
    assert record.work_order_id == first.pk
    assert record.asset_id == asset.pk
    assert record.total_cost == cost.total_cost
    assert record.downtime_minutes == 45
    assert record.maintenance_date == timezone.localdate()
    assert asset.status == AssetStatus.ACTIVE
    assert asset.purchase_cost == 100000
    assert asset.current_book_value == 100000
    assert AuditLog.objects.filter(action="WORK_ORDER_COMPLETED").exists()
    assert AuditLog.objects.filter(action="MAINTENANCE_RECORD_CREATED").exists()
    with pytest.raises(ValidationError, match="immutable"):
        record.summary = "Changed history"
        record.save()
    with pytest.raises(ValidationError, match="terminal"):
        create_maintenance_cost(
            actor=asset_manager,
            work_order_id=first.pk,
            cost_type="LABOR",
            description="Late charge",
            quantity="1",
            unit_cost="1",
        )


@pytest.mark.django_db
def test_multiple_active_orders_keep_asset_in_maintenance_until_last_closes(
    asset_factory, work_order_factory, asset_manager
):
    asset = asset_factory()
    one = work_order_factory(asset)
    two = work_order_factory(asset)
    start_work_order(work_order_id=one.pk, actor=asset_manager)
    start_work_order(work_order_id=two.pk, actor=asset_manager)
    complete_work_order(work_order_id=one.pk, actor=asset_manager, resolution="First repair")
    asset.refresh_from_db()
    assert asset.status == AssetStatus.IN_MAINTENANCE
    complete_work_order(work_order_id=two.pk, actor=asset_manager, resolution="Second repair")
    asset.refresh_from_db()
    assert asset.status == AssetStatus.ACTIVE


@pytest.mark.django_db
def test_cancel_work_order_restores_asset_when_last_started_order_is_cancelled(
    asset_factory, work_order_factory, asset_manager
):
    asset = asset_factory()
    order = work_order_factory(asset)
    start_work_order(work_order_id=order.pk, actor=asset_manager)
    cancel_work_order(work_order_id=order.pk, actor=asset_manager, reason="No longer needed")
    asset.refresh_from_db()
    assert asset.status == AssetStatus.ACTIVE
    with pytest.raises(ValidationError):
        complete_work_order(work_order_id=order.pk, actor=asset_manager, resolution="bad")


@pytest.mark.django_db
def test_audit_failure_rolls_back_start_and_completion_record(
    asset_factory, asset_manager, work_order_factory
):
    asset = asset_factory()
    order = work_order_factory(asset)
    with patch("maintenance.services.record_event", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError):
            start_work_order(work_order_id=order.pk, actor=asset_manager)
    order.refresh_from_db()
    asset.refresh_from_db()
    assert order.status == WorkOrderStatus.OPEN
    assert asset.status == AssetStatus.ACTIVE

    start_work_order(work_order_id=order.pk, actor=asset_manager)
    with patch("maintenance.services.record_event", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError):
            complete_work_order(work_order_id=order.pk, actor=asset_manager, resolution="Done")
    order.refresh_from_db()
    asset.refresh_from_db()
    assert order.status == WorkOrderStatus.IN_PROGRESS
    assert asset.status == AssetStatus.IN_MAINTENANCE
    assert not MaintenanceRecord.objects.exists()

    with patch.object(MaintenanceRecord, "save", side_effect=RuntimeError("record write failed")):
        with pytest.raises(RuntimeError):
            complete_work_order(work_order_id=order.pk, actor=asset_manager, resolution="Done")
    order.refresh_from_db()
    asset.refresh_from_db()
    assert order.status == WorkOrderStatus.IN_PROGRESS
    assert asset.status == AssetStatus.IN_MAINTENANCE
    assert not MaintenanceRecord.objects.exists()


@pytest.mark.django_db
def test_cross_organization_assignment_and_cost_references_are_rejected(
    asset_manager, other_org_user, asset_factory, work_order_factory
):
    order = work_order_factory()
    with pytest.raises(ValidationError, match="organization"):
        assign_work_order(work_order_id=order.pk, assigned_to=other_org_user, actor=asset_manager)


@pytest.mark.django_db
def test_negative_costs_are_rejected_and_terminal_orders_are_immutable(
    asset_manager, work_order_factory
):
    order = work_order_factory()
    for values in (("-1.000", "10.00"), ("1.000", "-10.00")):
        with pytest.raises(ValidationError):
            create_maintenance_cost(
                actor=asset_manager,
                work_order_id=order.pk,
                cost_type="OTHER",
                description="Invalid value",
                quantity=values[0],
                unit_cost=values[1],
            )
    start_work_order(work_order_id=order.pk, actor=asset_manager)
    complete_work_order(work_order_id=order.pk, actor=asset_manager, resolution="Finished")
    order.refresh_from_db()
    order.description = "Edit of completed record"
    with pytest.raises(ValidationError, match="immutable"):
        order.save()
    assert WorkOrder.objects.get(pk=order.pk).description == "Replace worn belt"


@pytest.mark.django_db(transaction=True)
def test_simultaneous_completion_produces_one_record(
    asset_factory, asset_manager, work_order_factory
):
    from accounts.models import User
    from maintenance.services import create_work_order

    asset = asset_factory()
    order = create_work_order(
        actor=asset_manager,
        asset_id=asset.pk,
        maintenance_type="CORRECTIVE",
        description="Race test",
    )
    start_work_order(work_order_id=order.pk, actor=asset_manager)
    barrier = Barrier(2)

    def finish():
        close_old_connections()
        try:
            actor = User.objects.get(pk=asset_manager.pk)
            barrier.wait(timeout=10)
            try:
                complete_work_order(
                    work_order_id=order.pk, actor=actor, resolution="Race completion"
                )
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
    assert MaintenanceRecord.objects.filter(work_order=order).count() == 1
