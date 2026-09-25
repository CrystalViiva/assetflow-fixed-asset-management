"""Immutable accounting snapshots for derecognized assets."""

import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from assets.models import CurrencyCode


class DisposalMethod(models.TextChoices):
    SALE = "SALE", "Sale"
    SCRAP = "SCRAP", "Scrap"
    DONATION = "DONATION", "Donation"
    WRITE_OFF = "WRITE_OFF", "Write-off"
    TRANSFER_OUT = "TRANSFER_OUT", "Transfer out"


class DisposalStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"
    COMPLETED = "COMPLETED", "Completed"


class Disposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="disposals"
    )
    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, related_name="disposals")
    disposal_date = models.DateField()
    disposal_method = models.CharField(max_length=12, choices=DisposalMethod.choices)
    reason = models.TextField()
    proceeds = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=3, choices=CurrencyCode.choices)
    capitalized_cost_at_disposal = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    accumulated_depreciation_at_disposal = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    carrying_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    gain_or_loss = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=DisposalStatus.choices, default=DisposalStatus.DRAFT
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="disposals_requested",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="disposals_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="disposals_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="disposals_rejected",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="disposals_cancelled",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="disposals_created"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="disposals_updated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-disposal_date", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("asset",),
                condition=Q(
                    status__in=(
                        DisposalStatus.DRAFT,
                        DisposalStatus.PENDING_APPROVAL,
                        DisposalStatus.APPROVED,
                    )
                ),
                name="uniq_open_disposal_asset",
            ),
            models.UniqueConstraint(
                fields=("asset",),
                condition=Q(status=DisposalStatus.COMPLETED),
                name="uniq_completed_disposal_asset",
            ),
            models.CheckConstraint(
                condition=Q(proceeds__gte=0), name="disposal_proceeds_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(disposal_method__in=DisposalMethod.values), name="disposal_method_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=DisposalStatus.values), name="disposal_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(currency__in=CurrencyCode.values), name="disposal_currency_valid"
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status__in=(DisposalStatus.APPROVED, DisposalStatus.COMPLETED))
                    | ~Q(approved_by=F("requested_by"))
                ),
                name="disposal_separation_of_duties",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=DisposalStatus.DRAFT,
                        submitted_at__isnull=True,
                        submitted_by__isnull=True,
                        approved_at__isnull=True,
                        approved_by__isnull=True,
                        rejected_at__isnull=True,
                        rejected_by__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        completed_at__isnull=True,
                        carrying_amount__isnull=True,
                        gain_or_loss__isnull=True,
                        capitalized_cost_at_disposal__isnull=True,
                        accumulated_depreciation_at_disposal__isnull=True,
                    )
                    | Q(
                        status=DisposalStatus.PENDING_APPROVAL,
                        submitted_at__isnull=False,
                        submitted_by__isnull=False,
                        approved_at__isnull=True,
                        approved_by__isnull=True,
                        rejected_at__isnull=True,
                        rejected_by__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        completed_at__isnull=True,
                        carrying_amount__isnull=True,
                        gain_or_loss__isnull=True,
                        capitalized_cost_at_disposal__isnull=True,
                        accumulated_depreciation_at_disposal__isnull=True,
                    )
                    | Q(
                        status=DisposalStatus.APPROVED,
                        submitted_at__isnull=False,
                        submitted_by__isnull=False,
                        approved_at__isnull=False,
                        approved_by__isnull=False,
                        rejected_at__isnull=True,
                        rejected_by__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        completed_at__isnull=True,
                        carrying_amount__isnull=True,
                        gain_or_loss__isnull=True,
                        capitalized_cost_at_disposal__isnull=True,
                        accumulated_depreciation_at_disposal__isnull=True,
                    )
                    | Q(
                        status=DisposalStatus.REJECTED,
                        submitted_at__isnull=False,
                        rejected_at__isnull=False,
                        rejected_by__isnull=False,
                        approved_at__isnull=True,
                        approved_by__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        completed_at__isnull=True,
                        carrying_amount__isnull=True,
                        gain_or_loss__isnull=True,
                        capitalized_cost_at_disposal__isnull=True,
                        accumulated_depreciation_at_disposal__isnull=True,
                    )
                    | Q(
                        status=DisposalStatus.CANCELLED,
                        cancelled_at__isnull=False,
                        cancelled_by__isnull=False,
                        rejected_at__isnull=True,
                        rejected_by__isnull=True,
                        completed_at__isnull=True,
                        carrying_amount__isnull=True,
                        gain_or_loss__isnull=True,
                        capitalized_cost_at_disposal__isnull=True,
                        accumulated_depreciation_at_disposal__isnull=True,
                    )
                    | Q(
                        status=DisposalStatus.COMPLETED,
                        submitted_at__isnull=False,
                        approved_at__isnull=False,
                        approved_by__isnull=False,
                        completed_at__isnull=False,
                        capitalized_cost_at_disposal__isnull=False,
                        accumulated_depreciation_at_disposal__isnull=False,
                        carrying_amount__isnull=False,
                        gain_or_loss__isnull=False,
                        rejected_at__isnull=True,
                        rejected_by__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                    )
                ),
                name="disposal_workflow_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status=DisposalStatus.COMPLETED)
                    | (
                        Q(capitalized_cost_at_disposal__gte=0)
                        & Q(accumulated_depreciation_at_disposal__gte=0)
                        & Q(carrying_amount__gte=0)
                        & Q(
                            accumulated_depreciation_at_disposal__lte=F(
                                "capitalized_cost_at_disposal"
                            )
                        )
                        & Q(
                            carrying_amount=F("capitalized_cost_at_disposal")
                            - F("accumulated_depreciation_at_disposal")
                        )
                        & Q(gain_or_loss=F("proceeds") - F("carrying_amount"))
                    )
                ),
                name="disposal_snapshot_matches",
            ),
            models.CheckConstraint(
                condition=Q(submitted_at__isnull=True) | Q(submitted_at__gte=F("created_at")),
                name="disposal_submit_after_create",
            ),
            models.CheckConstraint(
                condition=Q(approved_at__isnull=True) | Q(approved_at__gte=F("submitted_at")),
                name="disposal_approve_after_submit",
            ),
            models.CheckConstraint(
                condition=Q(completed_at__isnull=True) | Q(completed_at__gte=F("approved_at")),
                name="disposal_complete_after_approve",
            ),
            models.CheckConstraint(
                condition=Q(rejected_at__isnull=True) | Q(rejected_at__gte=F("submitted_at")),
                name="disposal_reject_after_submit",
            ),
            models.CheckConstraint(
                condition=Q(cancelled_at__isnull=True) | Q(cancelled_at__gte=F("created_at")),
                name="disposal_cancel_after_create",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "status", "disposal_date"),
                name="disposal_org_status_date_idx",
            ),
            models.Index(fields=("organization", "asset"), name="disposal_org_asset_idx"),
            models.Index(
                fields=("organization", "disposal_method", "disposal_date"),
                name="disposal_method_date_idx",
            ),
            models.Index(
                fields=("organization", "requested_by"), name="disposal_org_requester_idx"
            ),
            models.Index(fields=("organization", "approved_by"), name="disposal_org_approver_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.asset_id and self.organization_id:
            if self.asset.organization_id != self.organization_id:
                errors["asset"] = "Disposal and asset must belong to the same organization."
        for field in (
            "requested_by",
            "submitted_by",
            "approved_by",
            "rejected_by",
            "cancelled_by",
            "created_by",
            "updated_by",
        ):
            user = getattr(self, field, None)
            if user and user.organization_id != self.organization_id:
                errors[field] = "User must belong to the disposal organization."
        if self.organization_id and self.currency != self.organization.currency:
            errors["currency"] = "Disposal currency must match the organization's base currency."
        if self.asset_id and self.asset.capitalization_date and self.disposal_date:
            if self.disposal_date < self.asset.capitalization_date:
                errors["disposal_date"] = "Disposal date cannot precede capitalization."
        try:
            proceeds = Decimal(str(self.proceeds)) if self.proceeds is not None else None
        except InvalidOperation:
            proceeds = None
        if proceeds is not None and proceeds < 0:
            errors["proceeds"] = "Proceeds cannot be negative."
        if self.status == DisposalStatus.COMPLETED:
            if self.approved_by_id == self.requested_by_id:
                errors["approved_by"] = "The requester cannot approve their own disposal."
            if (
                self.capitalized_cost_at_disposal is not None
                and self.accumulated_depreciation_at_disposal is not None
            ):
                if self.accumulated_depreciation_at_disposal > self.capitalized_cost_at_disposal:
                    errors["accumulated_depreciation_at_disposal"] = (
                        "Accumulated depreciation cannot exceed capitalized cost."
                    )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status == DisposalStatus.COMPLETED:
                if any(
                    field.name not in {"id", "updated_at"}
                    and getattr(previous, field.attname) != getattr(self, field.attname)
                    for field in self._meta.concrete_fields
                ):
                    raise ValidationError("Completed disposal accounting history is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Disposal records cannot be deleted.")

    def __str__(self):
        return f"{self.asset.asset_tag} disposal ({self.status})"
