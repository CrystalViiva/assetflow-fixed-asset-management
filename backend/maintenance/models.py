"""Operational work orders and immutable maintenance history."""

import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Round
from django.utils import timezone


class MaintenanceType(models.TextChoices):
    PREVENTIVE = "PREVENTIVE", "Preventive"
    CORRECTIVE = "CORRECTIVE", "Corrective"
    INSPECTION = "INSPECTION", "Inspection"
    EMERGENCY = "EMERGENCY", "Emergency"


class FrequencyUnit(models.TextChoices):
    DAYS = "DAYS", "Days"
    WEEKS = "WEEKS", "Weeks"
    MONTHS = "MONTHS", "Months"


class WorkOrderPriority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class WorkOrderStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    ASSIGNED = "ASSIGNED", "Assigned"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class MaintenanceCostType(models.TextChoices):
    LABOR = "LABOR", "Labor"
    PARTS = "PARTS", "Parts"
    SERVICE = "SERVICE", "Service"
    OTHER = "OTHER", "Other"


class MaintenancePlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="maintenance_plans"
    )
    asset = models.ForeignKey(
        "assets.Asset", on_delete=models.PROTECT, related_name="maintenance_plans"
    )
    maintenance_type = models.CharField(max_length=12, choices=MaintenanceType.choices)
    frequency_value = models.PositiveIntegerField(
        validators=[MinValueValidator(1, message="Frequency must be positive.")]
    )
    frequency_unit = models.CharField(max_length=6, choices=FrequencyUnit.choices)
    next_due_date = models.DateField()
    active = models.BooleanField(default=True)
    instructions = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="maintenance_plans_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("next_due_date", "asset__asset_tag")
        constraints = [
            models.CheckConstraint(
                condition=Q(frequency_value__gt=0), name="maint_plan_freq_positive"
            ),
            models.CheckConstraint(
                condition=Q(maintenance_type__in=MaintenanceType.values),
                name="maint_plan_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(frequency_unit__in=FrequencyUnit.values), name="maint_plan_unit_valid"
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "asset"), name="maint_plan_org_asset_idx"),
            models.Index(
                fields=("organization", "active", "next_due_date"), name="maint_plan_due_idx"
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.organization_id
            and self.asset_id
            and self.asset.organization_id != self.organization_id
        ):
            errors["asset"] = "Asset and plan must belong to the same organization."
        if self.asset_id and self.active and self.asset.status == "DISPOSED":
            errors["asset"] = "Disposed assets cannot have active maintenance plans."
        if self.frequency_value is not None and self.frequency_value <= 0:
            errors["frequency_value"] = "Frequency must be positive."
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        raise ValidationError("Maintenance plans are retained; deactivate a plan instead.")

    def __str__(self):
        return f"{self.asset.asset_tag} {self.maintenance_type} plan"


class WorkOrderSequence(models.Model):
    """Per-organization transactional number allocator; gaps are acceptable, collisions are not."""

    organization = models.OneToOneField(
        "organizations.Organization", primary_key=True, on_delete=models.PROTECT
    )
    next_value = models.PositiveBigIntegerField(default=1)


class WorkOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="work_orders"
    )
    work_order_number = models.CharField(max_length=32)
    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, related_name="work_orders")
    maintenance_type = models.CharField(max_length=12, choices=MaintenanceType.choices)
    priority = models.CharField(
        max_length=8, choices=WorkOrderPriority.choices, default=WorkOrderPriority.MEDIUM
    )
    status = models.CharField(
        max_length=12, choices=WorkOrderStatus.choices, default=WorkOrderStatus.OPEN
    )
    description = models.TextField()
    diagnosis = models.TextField(blank=True)
    resolution = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="work_orders_requested"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="work_orders_assigned",
    )
    due_date = models.DateField(null=True, blank=True)
    opened_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-opened_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "work_order_number"), name="uniq_wo_number_org"
            ),
            models.CheckConstraint(condition=~Q(work_order_number=""), name="wo_number_not_blank"),
            models.CheckConstraint(
                condition=Q(maintenance_type__in=MaintenanceType.values), name="wo_type_valid"
            ),
            models.CheckConstraint(
                condition=Q(priority__in=WorkOrderPriority.values), name="wo_priority_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=WorkOrderStatus.values), name="wo_status_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=WorkOrderStatus.OPEN,
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                    )
                    | Q(
                        status=WorkOrderStatus.ASSIGNED,
                        assigned_to__isnull=False,
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                    )
                    | Q(
                        status=WorkOrderStatus.IN_PROGRESS,
                        started_at__isnull=False,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                    )
                    | Q(
                        status=WorkOrderStatus.COMPLETED,
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        cancelled_at__isnull=True,
                    )
                    | Q(
                        status=WorkOrderStatus.CANCELLED,
                        completed_at__isnull=True,
                        cancelled_at__isnull=False,
                    )
                ),
                name="wo_workflow_state_valid",
            ),
            models.CheckConstraint(
                condition=Q(started_at__isnull=True) | Q(started_at__gte=F("opened_at")),
                name="wo_started_after_open",
            ),
            models.CheckConstraint(
                condition=Q(completed_at__isnull=True) | Q(completed_at__gte=F("started_at")),
                name="wo_completed_after_start",
            ),
            models.CheckConstraint(
                condition=Q(cancelled_at__isnull=True) | Q(cancelled_at__gte=F("opened_at")),
                name="wo_cancelled_after_open",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "asset", "status"), name="wo_org_asset_status_idx"
            ),
            models.Index(fields=("organization", "status", "due_date"), name="wo_status_due_idx"),
            models.Index(
                fields=("organization", "maintenance_type", "opened_at"), name="wo_type_opened_idx"
            ),
            models.Index(fields=("organization", "assigned_to"), name="wo_org_assignee_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.organization_id
            and self.asset_id
            and self.asset.organization_id != self.organization_id
        ):
            errors["asset"] = "Asset and work order must belong to the same organization."
        for field in ("requested_by", "assigned_to"):
            user = getattr(self, field, None)
            if user and user.organization_id != self.organization_id:
                errors[field] = "User must belong to the work order organization."
        if self.asset_id and self.asset.status == "DISPOSED":
            errors["asset"] = "Disposed assets cannot receive work orders."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status in {
                WorkOrderStatus.COMPLETED,
                WorkOrderStatus.CANCELLED,
            }:
                if any(
                    field.name not in {"id", "updated_at"}
                    and getattr(previous, field.attname) != getattr(self, field.attname)
                    for field in self._meta.concrete_fields
                ):
                    raise ValidationError("Terminal work order history is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Work orders are retained and cannot be deleted.")

    def __str__(self):
        return self.work_order_number


class MaintenanceCost(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="maintenance_costs"
    )
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name="costs")
    cost_type = models.CharField(max_length=8, choices=MaintenanceCostType.choices)
    description = models.CharField(max_length=240)
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    unit_cost = models.DecimalField(
        max_digits=20, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    total_cost = models.DecimalField(max_digits=24, decimal_places=2, editable=False)
    vendor_reference = models.CharField(max_length=128, blank=True)
    incurred_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="maintenance_costs_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("incurred_at", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(cost_type__in=MaintenanceCostType.values), name="maint_cost_type_valid"
            ),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="maint_cost_qty_positive"),
            models.CheckConstraint(
                condition=Q(unit_cost__gte=0), name="maint_cost_unit_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(total_cost=Round(F("quantity") * F("unit_cost"), precision=2)),
                name="maint_cost_total_matches",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "work_order"), name="maint_cost_org_wo_idx")
        ]

    def clean(self):
        super().clean()
        if self.work_order_id and self.organization_id != self.work_order.organization_id:
            raise ValidationError({"work_order": "Cost and work order must share an organization."})
        try:
            quantity = Decimal(str(self.quantity)) if self.quantity is not None else None
        except InvalidOperation:
            quantity = None
        try:
            unit_cost = Decimal(str(self.unit_cost)) if self.unit_cost is not None else None
        except InvalidOperation:
            unit_cost = None
        if quantity is not None and quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be positive."})
        if unit_cost is not None and unit_cost < 0:
            raise ValidationError({"unit_cost": "Unit cost cannot be negative."})

    def save(self, *args, **kwargs):
        self.total_cost = (Decimal(str(self.quantity)) * Decimal(str(self.unit_cost))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Maintenance costs are retained and cannot be deleted.")


class MaintenanceRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="maintenance_records"
    )
    asset = models.ForeignKey(
        "assets.Asset", on_delete=models.PROTECT, related_name="maintenance_records"
    )
    work_order = models.OneToOneField(
        WorkOrder, on_delete=models.PROTECT, related_name="maintenance_record"
    )
    maintenance_date = models.DateField()
    maintenance_type = models.CharField(max_length=12, choices=MaintenanceType.choices)
    summary = models.TextField()
    total_cost = models.DecimalField(
        max_digits=24, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    downtime_minutes = models.PositiveIntegerField(null=True, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="maintenance_records_performed",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-maintenance_date",)
        constraints = [
            models.CheckConstraint(
                condition=Q(total_cost__gte=0), name="maint_record_cost_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(maintenance_type__in=MaintenanceType.values),
                name="maint_record_type_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "asset", "maintenance_date"),
                name="maint_record_asset_date_idx",
            ),
            models.Index(
                fields=("organization", "maintenance_type", "maintenance_date"),
                name="maint_record_type_date_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.work_order_id:
            if (
                self.work_order.organization_id != self.organization_id
                or self.work_order.asset_id != self.asset_id
            ):
                raise ValidationError(
                    "Maintenance record and work order must reference the same "
                    "organization and asset."
                )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Maintenance records are immutable historical records.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Maintenance records cannot be deleted.")

    def __str__(self):
        return f"{self.asset.asset_tag} maintenance {self.maintenance_date}"
