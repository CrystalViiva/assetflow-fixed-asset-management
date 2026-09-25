"""Custody history and organization/location movement history for fixed assets."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class TransferStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    APPROVED = "APPROVED", "Approved"
    COMPLETED = "COMPLETED", "Completed"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"


def _different_relation(first, second):
    """A null-safe field comparison usable in a database check constraint."""
    return (
        Q(**{f"{first}__isnull": True, f"{second}__isnull": False})
        | Q(**{f"{first}__isnull": False, f"{second}__isnull": True})
        | (Q(**{f"{first}__isnull": False, f"{second}__isnull": False}) & ~Q(**{first: F(second)}))
    )


class AssetAssignment(models.Model):
    """A custody episode. Closed episodes are historical and immutable."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="asset_assignments"
    )
    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, related_name="assignments")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_assignments",
    )
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_assignments",
    )
    location = models.ForeignKey(
        "organizations.Location",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_assignments",
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    returned_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_assignments_returned",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_assignments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-assigned_at", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("asset",),
                condition=Q(returned_at__isnull=True),
                name="uniq_active_assign_asset",
            ),
            models.CheckConstraint(
                condition=Q(returned_at__isnull=True) | Q(returned_at__gte=F("assigned_at")),
                name="assign_dates_valid",
            ),
            models.CheckConstraint(
                condition=Q(returned_at__isnull=True, returned_by__isnull=True)
                | Q(returned_at__isnull=False, returned_by__isnull=False),
                name="assign_return_actor_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "asset", "returned_at"), name="assign_org_asset_idx"
            ),
            models.Index(fields=("organization", "assigned_to"), name="assign_org_user_idx"),
            models.Index(fields=("organization", "department"), name="assign_org_dept_idx"),
            models.Index(fields=("organization", "location"), name="assign_org_loc_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.returned_at and self.assigned_at and self.returned_at < self.assigned_at:
            errors["returned_at"] = "Return time cannot precede assignment time."
        if bool(self.returned_at) != bool(self.returned_by_id):
            errors["returned_at"] = "A returned assignment requires its return actor and timestamp."
        if self.organization_id and self.asset_id:
            if self.asset.organization_id != self.organization_id:
                errors["asset"] = "Asset must belong to the assignment organization."
        for field in ("assigned_to", "returned_by", "created_by", "department", "location"):
            related = getattr(self, field, None)
            if related and related.organization_id != self.organization_id:
                errors[field] = (
                    f"{field.replace('_', ' ').capitalize()} must belong to the organization."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.returned_at:
                changed = [
                    field.name
                    for field in self._meta.concrete_fields
                    if field.name not in {"id", "updated_at"}
                    and getattr(previous, field.attname) != getattr(self, field.attname)
                ]
                if changed:
                    raise ValidationError("Closed assignment history is immutable.")
            if previous and not previous.returned_at and self.returned_at:
                changed = [
                    field.name
                    for field in self._meta.concrete_fields
                    if field.name not in {"id", "returned_at", "returned_by", "updated_at"}
                    and getattr(previous, field.attname) != getattr(self, field.attname)
                ]
                if changed:
                    raise ValidationError("Return an assignment without changing its history.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Assignment history cannot be deleted.")

    def __str__(self):
        return f"{self.asset.asset_tag} custody from {self.assigned_at:%Y-%m-%d}"


class AssetTransfer(models.Model):
    """Approval workflow recording movement between department/location snapshots."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="asset_transfers"
    )
    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, related_name="transfers")
    from_department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_transfers_from",
    )
    from_location = models.ForeignKey(
        "organizations.Location",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_transfers_from",
    )
    to_department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_transfers_to",
    )
    to_location = models.ForeignKey(
        "organizations.Location",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_transfers_to",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_transfers_requested",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_transfers_approved",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_transfers_completed",
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_transfers_rejected",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_transfers_cancelled",
    )
    requested_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=TransferStatus.choices, default=TransferStatus.REQUESTED
    )
    reason = models.CharField(max_length=240)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-requested_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("asset",),
                condition=Q(status__in=(TransferStatus.REQUESTED, TransferStatus.APPROVED)),
                name="uniq_open_transfer_asset",
            ),
            models.CheckConstraint(
                condition=Q(status__in=TransferStatus.values), name="transfer_status_valid"
            ),
            models.CheckConstraint(
                condition=_different_relation("from_department", "to_department")
                | _different_relation("from_location", "to_location"),
                name="transfer_destination_differs",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=TransferStatus.REQUESTED,
                        approved_at__isnull=True,
                        approved_by__isnull=True,
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                        rejected_at__isnull=True,
                        rejected_by__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                    )
                    | Q(
                        status=TransferStatus.APPROVED,
                        approved_at__isnull=False,
                        approved_by__isnull=False,
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                        rejected_at__isnull=True,
                        rejected_by__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                    )
                    | Q(
                        status=TransferStatus.COMPLETED,
                        approved_at__isnull=False,
                        approved_by__isnull=False,
                        completed_at__isnull=False,
                        completed_by__isnull=False,
                        rejected_at__isnull=True,
                        rejected_by__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                    )
                    | Q(
                        status=TransferStatus.REJECTED,
                        approved_at__isnull=True,
                        approved_by__isnull=True,
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                        rejected_at__isnull=False,
                        rejected_by__isnull=False,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                    )
                    | Q(
                        status=TransferStatus.CANCELLED,
                        approved_at__isnull=True,
                        approved_by__isnull=True,
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                        rejected_at__isnull=True,
                        rejected_by__isnull=True,
                        cancelled_at__isnull=False,
                        cancelled_by__isnull=False,
                    )
                ),
                name="transfer_state_fields_valid",
            ),
            models.CheckConstraint(
                condition=Q(approved_at__isnull=True) | Q(approved_at__gte=F("requested_at")),
                name="transfer_approve_time_valid",
            ),
            models.CheckConstraint(
                condition=Q(completed_at__isnull=True) | Q(completed_at__gte=F("requested_at")),
                name="transfer_complete_time_valid",
            ),
            models.CheckConstraint(
                condition=Q(rejected_at__isnull=True) | Q(rejected_at__gte=F("requested_at")),
                name="transfer_reject_time_valid",
            ),
            models.CheckConstraint(
                condition=Q(cancelled_at__isnull=True) | Q(cancelled_at__gte=F("requested_at")),
                name="transfer_cancel_time_valid",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "status"), name="transfer_org_status_idx"),
            models.Index(fields=("organization", "asset"), name="transfer_org_asset_idx"),
            models.Index(fields=("organization", "requested_at"), name="transfer_org_req_idx"),
            models.Index(fields=("organization", "completed_at"), name="transfer_org_done_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.organization_id and self.asset_id:
            if self.asset.organization_id != self.organization_id:
                errors["asset"] = "Asset must belong to the transfer organization."
        for field in (
            "from_department",
            "from_location",
            "to_department",
            "to_location",
            "requested_by",
            "approved_by",
            "completed_by",
            "rejected_by",
            "cancelled_by",
        ):
            related = getattr(self, field, None)
            if related and related.organization_id != self.organization_id:
                errors[field] = (
                    f"{field.replace('_', ' ').capitalize()} must belong to the organization."
                )
        if (
            self.from_department_id == self.to_department_id
            and self.from_location_id == self.to_location_id
        ):
            errors["to_department"] = "Transfer destination must differ from its source."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status == TransferStatus.COMPLETED:
                changed = [
                    field.name
                    for field in self._meta.concrete_fields
                    if field.name not in {"id", "updated_at"}
                    and getattr(previous, field.attname) != getattr(self, field.attname)
                ]
                if changed:
                    raise ValidationError("Completed transfer history is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Transfer history cannot be deleted.")

    def __str__(self):
        return f"Transfer {self.asset.asset_tag}: {self.status}"
