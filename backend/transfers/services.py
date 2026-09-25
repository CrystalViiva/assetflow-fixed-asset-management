"""Transactional asset custody and transfer workflows."""

from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from assets.models import Asset, AssetStatus
from audit.services import record_event
from transfers.models import AssetAssignment, AssetTransfer, TransferStatus

MOVABLE_STATUSES = {
    AssetStatus.ACTIVE,
    AssetStatus.IN_MAINTENANCE,
    AssetStatus.TRANSFERRED,
    AssetStatus.IMPAIRED,
}
_UNSET = object()


def _organization(actor):
    if not getattr(actor, "organization_id", None):
        raise ValidationError(
            {"organization": "The authenticated user must belong to an organization."}
        )
    return actor.organization


def _same_org(value, organization, field):
    if value is not None and value.organization_id != organization.pk:
        raise ValidationError(
            {field: f"{field.replace('_', ' ').capitalize()} must belong to your organization."}
        )


def _locked_asset(asset_id, organization):
    try:
        asset = Asset.objects.select_for_update(of=("self",)).get(
            pk=asset_id, organization=organization
        )
    except Asset.DoesNotExist as exc:
        raise ValidationError({"asset": "The asset was not found in your organization."}) from exc
    if asset.status not in MOVABLE_STATUSES:
        raise ValidationError(
            {"asset": "This asset lifecycle state does not permit assignment or transfer."}
        )
    return asset


def _locked_transfer(transfer_id, organization):
    try:
        return AssetTransfer.objects.select_for_update(of=("self",)).get(
            pk=transfer_id, organization=organization, asset__organization=organization
        )
    except AssetTransfer.DoesNotExist as exc:
        raise ValidationError(
            {"transfer": "The transfer was not found in your organization."}
        ) from exc


def _value(value):
    if hasattr(value, "_meta"):
        return str(value.pk)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _unique_violation(exc, expected_name, message, field):
    diagnostic = getattr(exc.__cause__, "diag", None)
    if getattr(diagnostic, "constraint_name", None) == expected_name:
        raise ValidationError({field: message}) from exc
    raise exc


def assign_asset(
    *,
    asset_id,
    actor,
    assigned_to=None,
    department=_UNSET,
    location=_UNSET,
    assigned_at=None,
    notes="",
    ip_address=None,
):
    """Open one custody assignment, optionally establishing current organization/location."""
    organization = _organization(actor)
    _same_org(assigned_to, organization, "assigned_to")
    with transaction.atomic():
        asset = _locked_asset(asset_id, organization)
        if AssetAssignment.objects.filter(asset=asset, returned_at__isnull=True).exists():
            raise ValidationError({"asset": "The asset already has an active assignment."})
        chosen_department = asset.department if department is _UNSET else department
        chosen_location = asset.location if location is _UNSET else location
        _same_org(chosen_department, organization, "department")
        _same_org(chosen_location, organization, "location")
        assignment = AssetAssignment(
            organization=organization,
            asset=asset,
            assigned_to=assigned_to,
            department=chosen_department,
            location=chosen_location,
            assigned_at=assigned_at or timezone.now(),
            notes=notes,
            created_by=actor,
        )
        assignment.full_clean()
        try:
            assignment.save()
        except IntegrityError as exc:
            _unique_violation(
                exc,
                "uniq_active_assign_asset",
                "The asset already has an active assignment.",
                "asset",
            )

        changes = {
            "assigned_to": {"from": None, "to": _value(assigned_to)},
            "department": {"from": _value(asset.department), "to": _value(chosen_department)},
            "location": {"from": _value(asset.location), "to": _value(chosen_location)},
        }
        asset_changes = {}
        if department is not _UNSET and asset.department_id != getattr(department, "pk", None):
            asset_changes["department"] = {
                "from": _value(asset.department),
                "to": _value(department),
            }
            asset.department = department
        if location is not _UNSET and asset.location_id != getattr(location, "pk", None):
            asset_changes["location"] = {"from": _value(asset.location), "to": _value(location)}
            asset.location = location
        if asset_changes:
            asset.updated_by = actor
            asset.save(update_fields=(*asset_changes, "updated_by", "updated_at"))
        record_event(
            organization=organization,
            user=actor,
            action="ASSET_ASSIGNED",
            entity_type="ASSET_ASSIGNMENT",
            entity_id=assignment.pk,
            ip_address=ip_address,
            changes=changes,
            metadata={"asset_id": str(asset.pk), "asset_location_changes": asset_changes},
        )
    return assignment


def return_asset(*, asset_id, actor, assignment_id=None, returned_at=None, ip_address=None):
    """Close the active custody episode without deleting or rewriting its history."""
    organization = _organization(actor)
    with transaction.atomic():
        asset = _locked_asset(asset_id, organization)
        try:
            active_assignments = AssetAssignment.objects.select_for_update(of=("self",)).filter(
                organization=organization, asset=asset, returned_at__isnull=True
            )
            if assignment_id is not None:
                active_assignments = active_assignments.filter(pk=assignment_id)
            assignment = active_assignments.get()
        except AssetAssignment.DoesNotExist as exc:
            raise ValidationError(
                {"assignment": "The asset has no active assignment to return."}
            ) from exc
        assignment.returned_at = returned_at or timezone.now()
        assignment.returned_by = actor
        assignment.full_clean()
        assignment.save(update_fields=("returned_at", "returned_by", "updated_at"))
        record_event(
            organization=organization,
            user=actor,
            action="ASSET_ASSIGNMENT_RETURNED",
            entity_type="ASSET_ASSIGNMENT",
            entity_id=assignment.pk,
            ip_address=ip_address,
            changes={
                "returned_at": {"from": None, "to": assignment.returned_at.isoformat()},
                "returned_by": {"from": None, "to": str(actor.pk)},
            },
            metadata={"asset_id": str(asset.pk)},
        )
    return assignment


def request_transfer(
    *, asset_id, actor, to_department=_UNSET, to_location=_UNSET, reason, notes="", ip_address=None
):
    """Capture a transfer request against a locked snapshot of current asset placement."""
    organization = _organization(actor)
    with transaction.atomic():
        asset = _locked_asset(asset_id, organization)
        if to_department is _UNSET:
            to_department = asset.department
        if to_location is _UNSET:
            to_location = asset.location
        _same_org(to_department, organization, "to_department")
        _same_org(to_location, organization, "to_location")
        if asset.department_id == getattr(
            to_department, "pk", None
        ) and asset.location_id == getattr(to_location, "pk", None):
            raise ValidationError(
                {"destination": "Transfer destination must differ from current placement."}
            )
        transfer = AssetTransfer(
            organization=organization,
            asset=asset,
            from_department=asset.department,
            from_location=asset.location,
            to_department=to_department,
            to_location=to_location,
            requested_by=actor,
            reason=reason,
            notes=notes,
        )
        transfer.full_clean()
        try:
            transfer.save()
        except IntegrityError as exc:
            _unique_violation(
                exc,
                "uniq_open_transfer_asset",
                "This asset already has a pending transfer request.",
                "asset",
            )
        record_event(
            organization=organization,
            user=actor,
            action="ASSET_TRANSFER_REQUESTED",
            entity_type="ASSET_TRANSFER",
            entity_id=transfer.pk,
            ip_address=ip_address,
            changes={
                "from_department": {"from": None, "to": _value(asset.department)},
                "from_location": {"from": None, "to": _value(asset.location)},
                "to_department": {"from": None, "to": _value(to_department)},
                "to_location": {"from": None, "to": _value(to_location)},
                "status": {"from": None, "to": transfer.status},
            },
            metadata={"asset_id": str(asset.pk), "reason": reason},
        )
    return transfer


def _transition_transfer(
    *, transfer_id, actor, next_status, actor_field, timestamp_field, audit_action, ip_address=None
):
    organization = _organization(actor)
    with transaction.atomic():
        transfer = _locked_transfer(transfer_id, organization)
        if transfer.status != "REQUESTED":
            raise ValidationError({"status": "Only a requested transfer can take this action."})
        before = transfer.status
        setattr(transfer, actor_field, actor)
        setattr(transfer, timestamp_field, timezone.now())
        transfer.status = next_status
        transfer.full_clean()
        transfer.save(update_fields=(actor_field, timestamp_field, "status", "updated_at"))
        record_event(
            organization=organization,
            user=actor,
            action=audit_action,
            entity_type="ASSET_TRANSFER",
            entity_id=transfer.pk,
            ip_address=ip_address,
            changes={"status": {"from": before, "to": next_status}},
            metadata={"asset_id": str(transfer.asset_id)},
        )
    return transfer


def approve_transfer(*, transfer_id, actor, ip_address=None):
    return _transition_transfer(
        transfer_id=transfer_id,
        actor=actor,
        next_status="APPROVED",
        actor_field="approved_by",
        timestamp_field="approved_at",
        audit_action="ASSET_TRANSFER_APPROVED",
        ip_address=ip_address,
    )


def reject_transfer(*, transfer_id, actor, ip_address=None):
    return _transition_transfer(
        transfer_id=transfer_id,
        actor=actor,
        next_status="REJECTED",
        actor_field="rejected_by",
        timestamp_field="rejected_at",
        audit_action="ASSET_TRANSFER_REJECTED",
        ip_address=ip_address,
    )


def cancel_transfer(*, transfer_id, actor, ip_address=None):
    return _transition_transfer(
        transfer_id=transfer_id,
        actor=actor,
        next_status="CANCELLED",
        actor_field="cancelled_by",
        timestamp_field="cancelled_at",
        audit_action="ASSET_TRANSFER_CANCELLED",
        ip_address=ip_address,
    )


def complete_transfer(*, transfer_id, actor, ip_address=None):
    """Atomically apply an approved placement change and finalize its immutable history."""
    organization = _organization(actor)
    with transaction.atomic():
        transfer = _locked_transfer(transfer_id, organization)
        try:
            asset = Asset.objects.select_for_update(of=("self",)).get(
                pk=transfer.asset_id, organization=organization
            )
        except Asset.DoesNotExist as exc:
            raise ValidationError(
                {"asset": "The transfer asset was not found in your organization."}
            ) from exc
        if transfer.status != "APPROVED":
            raise ValidationError({"status": "Only an approved transfer can be completed."})
        if asset.status not in MOVABLE_STATUSES:
            raise ValidationError({"asset": "This asset lifecycle state does not permit transfer."})
        if (
            asset.department_id != transfer.from_department_id
            or asset.location_id != transfer.from_location_id
        ):
            raise ValidationError(
                {"source": "Asset placement changed after this transfer was requested."}
            )
        before = {"department": _value(asset.department), "location": _value(asset.location)}
        asset.department = transfer.to_department
        asset.location = transfer.to_location
        asset.updated_by = actor
        asset.save(update_fields=("department", "location", "updated_by", "updated_at"))

        transfer.completed_by = actor
        transfer.completed_at = timezone.now()
        transfer.status = TransferStatus.COMPLETED
        transfer.full_clean()
        transfer.save(update_fields=("completed_by", "completed_at", "status", "updated_at"))
        changes = {
            "department": {"from": before["department"], "to": _value(asset.department)},
            "location": {"from": before["location"], "to": _value(asset.location)},
            "status": {"from": "APPROVED", "to": transfer.status},
        }
        record_event(
            organization=organization,
            user=actor,
            action="ASSET_TRANSFER_COMPLETED",
            entity_type="ASSET_TRANSFER",
            entity_id=transfer.pk,
            ip_address=ip_address,
            changes=changes,
            metadata={"asset_id": str(asset.pk), "asset_status_preserved": asset.status},
        )
    return transfer
