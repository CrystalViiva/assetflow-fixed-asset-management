"""Transactional maintenance workflow operations."""

from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from assets.models import Asset, AssetStatus
from audit.services import record_event
from maintenance.models import (
    MaintenanceCost,
    MaintenancePlan,
    MaintenanceRecord,
    WorkOrder,
    WorkOrderSequence,
    WorkOrderStatus,
)

MOVABLE_MAINTENANCE_ASSET_STATES = {
    AssetStatus.ACTIVE,
    AssetStatus.IN_MAINTENANCE,
    AssetStatus.TRANSFERRED,
    AssetStatus.IMPAIRED,
}
ACTIVE_WORK_ORDER_STATES = (WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS)


def _organization(actor):
    if not getattr(actor, "organization_id", None):
        raise ValidationError({"organization": "The user must belong to an organization."})
    return actor.organization


def _locked_asset(asset_id, organization):
    try:
        asset = Asset.objects.select_for_update(of=("self",)).get(
            pk=asset_id, organization=organization
        )
    except Asset.DoesNotExist as exc:
        raise ValidationError({"asset": "Asset was not found in your organization."}) from exc
    if asset.status not in MOVABLE_MAINTENANCE_ASSET_STATES:
        raise ValidationError({"asset": "This lifecycle state does not permit maintenance."})
    return asset


def _locked_work_order(work_order_id, organization):
    try:
        return (
            WorkOrder.objects.select_for_update(of=("self",))
            .select_related("asset")
            .get(pk=work_order_id, organization=organization, asset__organization=organization)
        )
    except WorkOrder.DoesNotExist as exc:
        raise ValidationError(
            {"work_order": "Work order was not found in your organization."}
        ) from exc


def _same_org(value, organization, field):
    if value is not None and value.organization_id != organization.pk:
        raise ValidationError({field: "This reference must belong to your organization."})


def _audit_value(value):
    if hasattr(value, "pk"):
        return str(value.pk)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _next_work_order_number(organization):
    """Allocate a per-organization monotonically increasing number under row lock."""
    try:
        with transaction.atomic():
            WorkOrderSequence.objects.create(organization=organization, next_value=2)
        return "WO-000001"
    except IntegrityError:
        # Concurrent first creation won the unique organization key; use its row below.
        pass
    sequence = WorkOrderSequence.objects.select_for_update().get(organization=organization)
    number = sequence.next_value
    sequence.next_value += 1
    sequence.save(update_fields=("next_value",))
    return f"WO-{number:06d}"


def create_maintenance_plan(
    *,
    actor,
    asset_id,
    maintenance_type,
    frequency_value,
    frequency_unit,
    next_due_date,
    active=True,
    instructions="",
    ip_address=None,
):
    organization = _organization(actor)
    with transaction.atomic():
        try:
            asset = Asset.objects.select_for_update(of=("self",)).get(
                pk=asset_id, organization=organization
            )
        except Asset.DoesNotExist as exc:
            raise ValidationError({"asset": "Asset was not found in your organization."}) from exc
        if active and asset.status == AssetStatus.DISPOSED:
            raise ValidationError(
                {"asset": "Disposed assets cannot have active maintenance plans."}
            )
        plan = MaintenancePlan(
            organization=organization,
            asset=asset,
            maintenance_type=maintenance_type,
            frequency_value=frequency_value,
            frequency_unit=frequency_unit,
            next_due_date=next_due_date,
            active=active,
            instructions=instructions,
            created_by=actor,
        )
        plan.full_clean()
        plan.save()
        record_event(
            organization=organization,
            user=actor,
            action="MAINTENANCE_PLAN_CREATED",
            entity_type="MAINTENANCE_PLAN",
            entity_id=plan.pk,
            ip_address=ip_address,
            metadata={"asset_id": str(asset.pk), "maintenance_type": plan.maintenance_type},
        )
    return plan


def update_maintenance_plan(*, plan_id, actor, changes, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        try:
            plan = (
                MaintenancePlan.objects.select_for_update(of=("self",))
                .select_related("asset")
                .get(pk=plan_id, organization=organization)
            )
        except MaintenancePlan.DoesNotExist as exc:
            raise ValidationError(
                {"plan": "Maintenance plan was not found in your organization."}
            ) from exc
        before = {key: _audit_value(getattr(plan, key)) for key in changes}
        for key, value in changes.items():
            setattr(plan, key, value)
        if plan.asset.status == AssetStatus.DISPOSED and plan.active:
            raise ValidationError(
                {"asset": "Disposed assets cannot have active maintenance plans."}
            )
        plan.full_clean()
        plan.save()
        after = {key: _audit_value(getattr(plan, key)) for key in changes}
        record_event(
            organization=organization,
            user=actor,
            action="MAINTENANCE_PLAN_UPDATED",
            entity_type="MAINTENANCE_PLAN",
            entity_id=plan.pk,
            ip_address=ip_address,
            changes={key: {"from": before[key], "to": after[key]} for key in changes},
        )
    return plan


def create_work_order(
    *,
    actor,
    asset_id,
    maintenance_type,
    description,
    priority="MEDIUM",
    due_date=None,
    diagnosis="",
    ip_address=None,
):
    organization = _organization(actor)
    with transaction.atomic():
        asset = _locked_asset(asset_id, organization)
        number = _next_work_order_number(organization)
        work_order = WorkOrder(
            organization=organization,
            work_order_number=number,
            asset=asset,
            maintenance_type=maintenance_type,
            priority=priority,
            description=description,
            diagnosis=diagnosis,
            requested_by=actor,
            due_date=due_date,
        )
        work_order.full_clean()
        work_order.save()
        record_event(
            organization=organization,
            user=actor,
            action="WORK_ORDER_CREATED",
            entity_type="WORK_ORDER",
            entity_id=work_order.pk,
            ip_address=ip_address,
            metadata={"asset_id": str(asset.pk), "work_order_number": number},
        )
    return work_order


def assign_work_order(*, work_order_id, assigned_to, actor, ip_address=None):
    organization = _organization(actor)
    _same_org(assigned_to, organization, "assigned_to")
    with transaction.atomic():
        work_order = _locked_work_order(work_order_id, organization)
        _locked_asset(work_order.asset_id, organization)
        if work_order.status != WorkOrderStatus.OPEN:
            raise ValidationError({"status": "Only an open work order can be assigned."})
        work_order.assigned_to = assigned_to
        work_order.status = WorkOrderStatus.ASSIGNED
        work_order.full_clean()
        work_order.save(update_fields=("assigned_to", "status", "updated_at"))
        record_event(
            organization=organization,
            user=actor,
            action="WORK_ORDER_ASSIGNED",
            entity_type="WORK_ORDER",
            entity_id=work_order.pk,
            ip_address=ip_address,
            changes={"assigned_to": {"from": None, "to": str(assigned_to.pk)}},
        )
    return work_order


def start_work_order(*, work_order_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        work_order = _locked_work_order(work_order_id, organization)
        asset = _locked_asset(work_order.asset_id, organization)
        if work_order.status not in {WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED}:
            raise ValidationError({"status": "Only open or assigned work orders can start."})
        if asset.status not in {
            AssetStatus.ACTIVE,
            AssetStatus.IN_MAINTENANCE,
            AssetStatus.TRANSFERRED,
            AssetStatus.IMPAIRED,
        }:
            raise ValidationError({"asset": "This lifecycle state does not permit maintenance."})
        before = asset.status
        if asset.status == AssetStatus.ACTIVE:
            asset.status = AssetStatus.IN_MAINTENANCE
            asset.updated_by = actor
            asset.save(update_fields=("status", "updated_by", "updated_at"))
        work_order.status = WorkOrderStatus.IN_PROGRESS
        work_order.started_at = timezone.now()
        work_order.full_clean()
        work_order.save(update_fields=("status", "started_at", "updated_at"))
        record_event(
            organization=organization,
            user=actor,
            action="WORK_ORDER_STARTED",
            entity_type="WORK_ORDER",
            entity_id=work_order.pk,
            ip_address=ip_address,
            changes={"status": {"from": "OPEN_OR_ASSIGNED", "to": work_order.status}},
            metadata={"asset_id": str(asset.pk)},
        )
        if before != asset.status:
            record_event(
                organization=organization,
                user=actor,
                action="ASSET_ENTERED_MAINTENANCE",
                entity_type="ASSET",
                entity_id=asset.pk,
                ip_address=ip_address,
                changes={"status": {"from": before, "to": asset.status}},
                metadata={"work_order_id": str(work_order.pk)},
            )
    return work_order


def _restore_asset_if_no_active_work(work_order, asset, actor, ip_address):
    active_exists = (
        WorkOrder.objects.filter(
            organization=work_order.organization,
            asset=asset,
            status__in=ACTIVE_WORK_ORDER_STATES,
        )
        .exclude(pk=work_order.pk)
        .exists()
    )
    if asset.status == AssetStatus.IN_MAINTENANCE and not active_exists:
        before = asset.status
        asset.status = AssetStatus.ACTIVE
        asset.updated_by = actor
        asset.save(update_fields=("status", "updated_by", "updated_at"))
        record_event(
            organization=work_order.organization,
            user=actor,
            action="ASSET_RETURNED_FROM_MAINTENANCE",
            entity_type="ASSET",
            entity_id=asset.pk,
            ip_address=ip_address,
            changes={"status": {"from": before, "to": asset.status}},
            metadata={"work_order_id": str(work_order.pk)},
        )


def complete_work_order(
    *,
    work_order_id,
    actor,
    resolution,
    completion_notes="",
    downtime_minutes=None,
    performed_by=None,
    maintenance_date=None,
    ip_address=None,
):
    organization = _organization(actor)
    if performed_by is not None:
        _same_org(performed_by, organization, "performed_by")
    with transaction.atomic():
        work_order = _locked_work_order(work_order_id, organization)
        asset = _locked_asset(work_order.asset_id, organization)
        if work_order.status != WorkOrderStatus.IN_PROGRESS:
            raise ValidationError({"status": "Only an in-progress work order can be completed."})
        if asset.status in {
            AssetStatus.DISPOSED,
            AssetStatus.DRAFT,
            AssetStatus.PENDING_CAPITALIZATION,
        }:
            raise ValidationError({"asset": "This lifecycle state does not permit completion."})
        total = work_order.costs.aggregate(total=Sum("total_cost"))["total"] or Decimal("0.00")
        completed_at = timezone.now()
        work_order.resolution = resolution
        work_order.completion_notes = completion_notes
        work_order.status = WorkOrderStatus.COMPLETED
        work_order.completed_at = completed_at
        work_order.full_clean()
        record = MaintenanceRecord(
            organization=organization,
            asset=asset,
            work_order=work_order,
            maintenance_date=maintenance_date or timezone.localdate(completed_at),
            maintenance_type=work_order.maintenance_type,
            summary=resolution or completion_notes or work_order.description,
            total_cost=total,
            downtime_minutes=downtime_minutes,
            performed_by=performed_by,
        )
        record.full_clean()
        record.save()
        work_order.save(
            update_fields=("resolution", "completion_notes", "status", "completed_at", "updated_at")
        )
        _restore_asset_if_no_active_work(work_order, asset, actor, ip_address)
        record_event(
            organization=organization,
            user=actor,
            action="WORK_ORDER_COMPLETED",
            entity_type="WORK_ORDER",
            entity_id=work_order.pk,
            ip_address=ip_address,
            changes={"status": {"from": "IN_PROGRESS", "to": work_order.status}},
            metadata={
                "asset_id": str(asset.pk),
                "maintenance_record_id": str(record.pk),
                "total_cost": str(total),
                "downtime_minutes": downtime_minutes,
            },
        )
        record_event(
            organization=organization,
            user=actor,
            action="MAINTENANCE_RECORD_CREATED",
            entity_type="MAINTENANCE_RECORD",
            entity_id=record.pk,
            ip_address=ip_address,
            metadata={"asset_id": str(asset.pk), "work_order_id": str(work_order.pk)},
        )
    return work_order, record


def cancel_work_order(*, work_order_id, actor, reason="", ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        work_order = _locked_work_order(work_order_id, organization)
        asset = _locked_asset(work_order.asset_id, organization)
        if work_order.status in {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}:
            raise ValidationError({"status": "A terminal work order cannot be cancelled."})
        before = work_order.status
        work_order.status = WorkOrderStatus.CANCELLED
        work_order.cancelled_at = timezone.now()
        if reason:
            work_order.completion_notes = reason
        work_order.full_clean()
        work_order.save(update_fields=("status", "cancelled_at", "completion_notes", "updated_at"))
        _restore_asset_if_no_active_work(work_order, asset, actor, ip_address)
        record_event(
            organization=organization,
            user=actor,
            action="WORK_ORDER_CANCELLED",
            entity_type="WORK_ORDER",
            entity_id=work_order.pk,
            ip_address=ip_address,
            changes={"status": {"from": before, "to": work_order.status}},
            metadata={"asset_id": str(asset.pk), "reason": reason},
        )
    return work_order


def create_maintenance_cost(
    *,
    actor,
    work_order_id,
    cost_type,
    description,
    quantity,
    unit_cost,
    vendor_reference="",
    incurred_at=None,
    ip_address=None,
):
    organization = _organization(actor)
    with transaction.atomic():
        work_order = _locked_work_order(work_order_id, organization)
        if work_order.status in {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}:
            raise ValidationError({"work_order": "Costs cannot be added to a terminal work order."})
        cost = MaintenanceCost(
            organization=organization,
            work_order=work_order,
            cost_type=cost_type,
            description=description,
            quantity=quantity,
            unit_cost=unit_cost,
            vendor_reference=vendor_reference,
            incurred_at=incurred_at or timezone.now(),
            created_by=actor,
        )
        cost.full_clean()
        cost.save()
        record_event(
            organization=organization,
            user=actor,
            action="MAINTENANCE_COST_CREATED",
            entity_type="MAINTENANCE_COST",
            entity_id=cost.pk,
            ip_address=ip_address,
            metadata={"work_order_id": str(work_order.pk), "total_cost": str(cost.total_cost)},
        )
    return cost
