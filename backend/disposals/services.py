"""Transactional disposal workflow and accounting derecognition services."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from assets.models import Asset, AssetStatus
from audit.services import record_event
from depreciation.services.engine import money
from disposals.models import Disposal, DisposalStatus
from maintenance.models import WorkOrderStatus
from transfers.models import AssetAssignment, AssetTransfer, TransferStatus


def _organization(actor):
    if not getattr(actor, "organization_id", None):
        raise ValidationError({"organization": "The user must belong to an organization."})
    return actor.organization


def _locked_disposal(disposal_id, organization):
    try:
        return Disposal.objects.select_for_update(of=("self",)).get(
            pk=disposal_id, organization=organization
        )
    except Disposal.DoesNotExist as exc:
        raise ValidationError({"disposal": "Disposal was not found in your organization."}) from exc


def _locked_asset(asset_id, organization):
    try:
        asset = Asset.objects.select_for_update(of=("self",)).get(
            pk=asset_id, organization=organization
        )
    except Asset.DoesNotExist as exc:
        raise ValidationError({"asset": "Asset was not found in your organization."}) from exc
    if asset.status != AssetStatus.ACTIVE:
        raise ValidationError({"asset": "Only ACTIVE assets are eligible for disposal."})
    if asset.capitalization_date is None:
        raise ValidationError({"asset": "The asset must be capitalized before disposal."})
    return asset


def _value(value):
    if hasattr(value, "pk"):
        return str(value.pk)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _raise_unique(exc):
    constraint = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
    if constraint in {"uniq_open_disposal_asset", "uniq_completed_disposal_asset"}:
        raise ValidationError(
            {"asset": "An active or completed disposal already exists for this asset."}
        ) from exc
    raise exc


def _audit(*, disposal, actor, action, before=None, after=None, metadata=None, ip_address=None):
    changes = {}
    if before is not None or after is not None:
        changes["status"] = {"from": before, "to": after}
    record_event(
        organization=disposal.organization,
        user=actor,
        action=action,
        entity_type="DISPOSAL",
        entity_id=disposal.pk,
        ip_address=ip_address,
        changes=changes,
        metadata={"asset_id": str(disposal.asset_id), **(metadata or {})},
    )


def create_disposal(
    *,
    actor,
    asset_id,
    disposal_date,
    disposal_method,
    reason,
    proceeds=Decimal("0.00"),
    currency=None,
    ip_address=None,
):
    organization = _organization(actor)
    with transaction.atomic():
        asset = _locked_asset(asset_id, organization)
        disposal = Disposal(
            organization=organization,
            asset=asset,
            disposal_date=disposal_date,
            disposal_method=disposal_method,
            reason=reason,
            proceeds=money(proceeds),
            currency=currency or organization.currency,
            requested_by=actor,
            created_by=actor,
            updated_by=actor,
        )
        disposal.full_clean()
        try:
            disposal.save()
        except IntegrityError as exc:
            _raise_unique(exc)
        _audit(
            disposal=disposal,
            actor=actor,
            action="DISPOSAL_CREATED",
            ip_address=ip_address,
            metadata={"method": disposal.disposal_method, "proceeds": str(disposal.proceeds)},
        )
    return disposal


def update_disposal(*, disposal_id, actor, changes, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        disposal = _locked_disposal(disposal_id, organization)
        asset = _locked_asset(disposal.asset_id, organization)
        if disposal.status != DisposalStatus.DRAFT:
            raise ValidationError({"status": "Only draft disposals can be edited."})
        allowed = {"disposal_date", "disposal_method", "reason", "proceeds", "currency"}
        if set(changes) - allowed:
            raise ValidationError({"fields": "Only draft disposal details can be updated."})
        before = {key: _value(getattr(disposal, key)) for key in changes}
        for key, value in changes.items():
            if key == "proceeds":
                value = money(value)
            setattr(disposal, key, value)
        disposal.updated_by = actor
        disposal.full_clean()
        disposal.save()
        audit_changes = {
            key: {"from": before[key], "to": _value(getattr(disposal, key))} for key in changes
        }
        record_event(
            organization=organization,
            user=actor,
            action="DISPOSAL_UPDATED",
            entity_type="DISPOSAL",
            entity_id=disposal.pk,
            ip_address=ip_address,
            changes=audit_changes,
            metadata={"asset_id": str(asset.pk)},
        )
    return disposal


def submit_disposal(*, disposal_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        disposal = _locked_disposal(disposal_id, organization)
        _locked_asset(disposal.asset_id, organization)
        if disposal.status != DisposalStatus.DRAFT:
            raise ValidationError({"status": "Only a draft disposal can be submitted."})
        before = disposal.status
        disposal.status = DisposalStatus.PENDING_APPROVAL
        disposal.submitted_by = actor
        disposal.submitted_at = timezone.now()
        disposal.updated_by = actor
        disposal.full_clean()
        disposal.save(
            update_fields=("status", "submitted_by", "submitted_at", "updated_by", "updated_at")
        )
        _audit(
            disposal=disposal,
            actor=actor,
            action="DISPOSAL_SUBMITTED",
            before=before,
            after=disposal.status,
            ip_address=ip_address,
        )
    return disposal


def approve_disposal(*, disposal_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        disposal = _locked_disposal(disposal_id, organization)
        _locked_asset(disposal.asset_id, organization)
        if disposal.status != DisposalStatus.PENDING_APPROVAL:
            raise ValidationError({"status": "Only a pending disposal can be approved."})
        if disposal.requested_by_id == actor.pk:
            raise ValidationError(
                {"approved_by": "The requester cannot approve their own disposal."}
            )
        before = disposal.status
        disposal.status = DisposalStatus.APPROVED
        disposal.approved_by = actor
        disposal.approved_at = timezone.now()
        disposal.updated_by = actor
        disposal.full_clean()
        disposal.save(
            update_fields=("status", "approved_by", "approved_at", "updated_by", "updated_at")
        )
        _audit(
            disposal=disposal,
            actor=actor,
            action="DISPOSAL_APPROVED",
            before=before,
            after=disposal.status,
            ip_address=ip_address,
        )
    return disposal


def reject_disposal(*, disposal_id, actor, reason="", ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        disposal = _locked_disposal(disposal_id, organization)
        if disposal.status != DisposalStatus.PENDING_APPROVAL:
            raise ValidationError({"status": "Only a pending disposal can be rejected."})
        before = disposal.status
        disposal.status = DisposalStatus.REJECTED
        disposal.rejected_by = actor
        disposal.rejected_at = timezone.now()
        disposal.updated_by = actor
        if reason:
            disposal.reason = reason
        disposal.full_clean()
        disposal.save(
            update_fields=(
                "status",
                "rejected_by",
                "rejected_at",
                "updated_by",
                "reason",
                "updated_at",
            )
        )
        _audit(
            disposal=disposal,
            actor=actor,
            action="DISPOSAL_REJECTED",
            before=before,
            after=disposal.status,
            metadata={"reason": reason},
            ip_address=ip_address,
        )
    return disposal


def cancel_disposal(*, disposal_id, actor, reason="", ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        disposal = _locked_disposal(disposal_id, organization)
        if disposal.status not in {
            DisposalStatus.DRAFT,
            DisposalStatus.PENDING_APPROVAL,
            DisposalStatus.APPROVED,
        }:
            raise ValidationError({"status": "This disposal can no longer be cancelled."})
        before = disposal.status
        disposal.status = DisposalStatus.CANCELLED
        disposal.cancelled_by = actor
        disposal.cancelled_at = timezone.now()
        disposal.updated_by = actor
        if reason:
            disposal.reason = reason
        disposal.full_clean()
        disposal.save(
            update_fields=(
                "status",
                "cancelled_by",
                "cancelled_at",
                "updated_by",
                "reason",
                "updated_at",
            )
        )
        _audit(
            disposal=disposal,
            actor=actor,
            action="DISPOSAL_CANCELLED",
            before=before,
            after=disposal.status,
            metadata={"reason": reason},
            ip_address=ip_address,
        )
    return disposal


def _assert_no_open_operations(disposal, asset):
    if AssetAssignment.objects.filter(asset=asset, returned_at__isnull=True).exists():
        raise ValidationError(
            {"asset": "Return the asset's active custody assignment before disposal."}
        )
    if AssetTransfer.objects.filter(
        asset=asset, status__in=(TransferStatus.REQUESTED, TransferStatus.APPROVED)
    ).exists():
        raise ValidationError({"asset": "Resolve the asset's open transfer before disposal."})
    from maintenance.models import WorkOrder

    if WorkOrder.objects.filter(
        asset=asset,
        status__in=(WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS),
    ).exists():
        raise ValidationError({"asset": "Resolve the asset's open work orders before disposal."})


def complete_disposal(*, disposal_id, actor, ip_address=None):
    """Lock and atomically derecognize an asset using its persisted carrying state."""
    organization = _organization(actor)
    with transaction.atomic():
        disposal = _locked_disposal(disposal_id, organization)
        asset = _locked_asset(disposal.asset_id, organization)
        if disposal.status != DisposalStatus.APPROVED:
            raise ValidationError({"status": "Only an approved disposal can be completed."})
        if disposal.approved_by_id == disposal.requested_by_id:
            raise ValidationError(
                {"approved_by": "The requester cannot approve their own disposal."}
            )
        if disposal.disposal_date > timezone.localdate():
            raise ValidationError({"disposal_date": "A future-dated disposal cannot be completed."})
        if disposal.currency != organization.currency:
            raise ValidationError(
                {"currency": "Disposal currency must match the organization's base currency."}
            )
        _assert_no_open_operations(disposal, asset)

        capitalized_cost = money(asset.purchase_cost)
        accumulated = money(asset.accumulated_depreciation)
        carrying_amount = money(capitalized_cost - accumulated)
        current_book_value = money(asset.current_book_value)
        residual_value = money(asset.residual_value)
        if capitalized_cost < 0 or accumulated < 0 or accumulated > capitalized_cost:
            raise ValidationError(
                {"asset": "The asset's capitalized cost and depreciation state are inconsistent."}
            )
        if carrying_amount < residual_value or carrying_amount != current_book_value:
            raise ValidationError(
                {"asset": "The asset carrying amount does not agree with its accounting state."}
            )

        before_status = disposal.status
        disposal.capitalized_cost_at_disposal = capitalized_cost
        disposal.accumulated_depreciation_at_disposal = accumulated
        disposal.carrying_amount = carrying_amount
        disposal.proceeds = money(disposal.proceeds)
        disposal.gain_or_loss = money(disposal.proceeds - carrying_amount)
        disposal.status = DisposalStatus.COMPLETED
        disposal.completed_at = timezone.now()
        disposal.updated_by = actor
        disposal.full_clean()
        disposal.save(
            update_fields=(
                "capitalized_cost_at_disposal",
                "accumulated_depreciation_at_disposal",
                "carrying_amount",
                "proceeds",
                "gain_or_loss",
                "status",
                "completed_at",
                "updated_by",
                "updated_at",
            )
        )

        asset.status = AssetStatus.DISPOSED
        asset.updated_by = actor
        asset.save(update_fields=("status", "updated_by", "updated_at"))
        snapshot = {
            "capitalized_cost": str(capitalized_cost),
            "accumulated_depreciation": str(accumulated),
            "carrying_amount": str(carrying_amount),
            "proceeds": str(disposal.proceeds),
            "gain_or_loss": str(disposal.gain_or_loss),
            "currency": disposal.currency,
        }
        record_event(
            organization=organization,
            user=actor,
            action="ASSET_DERECOGNIZED",
            entity_type="ASSET",
            entity_id=asset.pk,
            ip_address=ip_address,
            changes={"status": {"from": AssetStatus.ACTIVE, "to": AssetStatus.DISPOSED}},
            metadata={"disposal_id": str(disposal.pk), **snapshot},
        )
        _audit(
            disposal=disposal,
            actor=actor,
            action="DISPOSAL_COMPLETED",
            before=before_status,
            after=disposal.status,
            metadata=snapshot,
            ip_address=ip_address,
        )
    return disposal
