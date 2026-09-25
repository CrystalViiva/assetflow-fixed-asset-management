"""Accounting periods and append-only depreciation schedule/posting records."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from assets.models import DepreciationMethod


class PeriodStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    CLOSED = "CLOSED", "Closed"


class ScheduleStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    COMPLETE = "COMPLETE", "Complete"


class AccountingPeriod(models.Model):
    """Explicit organization-scoped calendar month; periods are never created by posting."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="accounting_periods"
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=8, choices=PeriodStatus.choices, default=PeriodStatus.OPEN)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="closed_accounting_periods",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-year", "-month")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "year", "month"), name="uniq_period_per_org"
            ),
            models.CheckConstraint(
                condition=Q(month__gte=1, month__lte=12), name="period_month_valid"
            ),
            models.CheckConstraint(
                condition=Q(year__gte=1900, year__lte=9999), name="period_year_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=PeriodStatus.values), name="period_status_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=PeriodStatus.OPEN, closed_at__isnull=True, closed_by__isnull=True)
                    | Q(
                        status=PeriodStatus.CLOSED, closed_at__isnull=False, closed_by__isnull=False
                    )
                ),
                name="period_closure_consistent",
            ),
        ]

    @property
    def first_day(self):
        from datetime import date

        return date(self.year, self.month, 1)

    def clean(self):
        super().clean()
        if self.status == PeriodStatus.OPEN and (self.closed_at or self.closed_by_id):
            raise ValidationError("An open period cannot have closure details.")
        if self.status == PeriodStatus.CLOSED and (not self.closed_at or not self.closed_by_id):
            raise ValidationError("A closed period requires a timestamp and closing actor.")

    def __str__(self):
        return f"{self.organization.code} {self.year:04d}-{self.month:02d}"


class DepreciationSchedule(models.Model):
    """Frozen SLM assumptions for an asset; revisions require a future controlled workflow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="depreciation_schedules",
    )
    asset = models.OneToOneField(
        "assets.Asset", on_delete=models.PROTECT, related_name="depreciation_schedule"
    )
    method = models.CharField(max_length=3, choices=DepreciationMethod.choices)
    capitalized_cost = models.DecimalField(max_digits=20, decimal_places=2)
    depreciable_base = models.DecimalField(max_digits=20, decimal_places=2)
    residual_value = models.DecimalField(max_digits=20, decimal_places=2)
    useful_life_months = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    periodic_depreciation = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(
        max_length=10, choices=ScheduleStatus.choices, default=ScheduleStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("asset__asset_tag",)
        constraints = [
            models.CheckConstraint(
                condition=Q(depreciable_base__gte=0), name="sched_base_nonnegative"
            ),
            models.CheckConstraint(condition=Q(capitalized_cost__gt=0), name="sched_cost_positive"),
            models.CheckConstraint(
                condition=Q(depreciable_base=F("capitalized_cost") - F("residual_value")),
                name="sched_base_matches_cost",
            ),
            models.CheckConstraint(
                condition=Q(residual_value__gte=0), name="sched_residual_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(useful_life_months__gt=0), name="sched_life_positive"
            ),
            models.CheckConstraint(
                condition=Q(periodic_depreciation__gte=0), name="sched_periodic_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")), name="sched_dates_valid"
            ),
            models.CheckConstraint(
                condition=Q(method=DepreciationMethod.SLM), name="sched_method_slm"
            ),
            models.CheckConstraint(
                condition=Q(status__in=ScheduleStatus.values), name="sched_status_valid"
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "status"), name="depr_sched_org_status_idx")
        ]

    def clean(self):
        super().clean()
        if (
            self.organization_id
            and self.asset_id
            and self.asset.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"asset": "Asset and schedule must belong to the same organization."}
            )
        if self.residual_value > self.capitalized_cost:
            raise ValidationError(
                {"residual_value": "Residual value cannot exceed capitalized cost."}
            )
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "Schedule end cannot precede its start."})

    def __str__(self):
        return f"Depreciation schedule: {self.asset.asset_tag}"


class DepreciationEntry(models.Model):
    """Posted monthly depreciation; entries are protected ledger history."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="depreciation_entries"
    )
    asset = models.ForeignKey(
        "assets.Asset", on_delete=models.PROTECT, related_name="depreciation_entries"
    )
    schedule = models.ForeignKey(
        DepreciationSchedule, on_delete=models.PROTECT, related_name="entries"
    )
    accounting_period = models.ForeignKey(
        AccountingPeriod, on_delete=models.PROTECT, related_name="depreciation_entries"
    )
    opening_book_value = models.DecimalField(max_digits=20, decimal_places=2)
    depreciation_amount = models.DecimalField(max_digits=20, decimal_places=2)
    accumulated_depreciation = models.DecimalField(max_digits=20, decimal_places=2)
    closing_book_value = models.DecimalField(max_digits=20, decimal_places=2)
    posted_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="depreciation_entries_created",
    )

    class Meta:
        ordering = ("accounting_period__year", "accounting_period__month", "asset__asset_tag")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "asset", "accounting_period"),
                name="uniq_asset_depreciation_period",
            ),
            models.CheckConstraint(
                condition=Q(opening_book_value__gte=0), name="entry_opening_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(depreciation_amount__gte=0), name="entry_amount_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(accumulated_depreciation__gte=0), name="entry_accum_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(closing_book_value__gte=0), name="entry_closing_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(closing_book_value=F("opening_book_value") - F("depreciation_amount")),
                name="entry_rollforward_matches",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "accounting_period"), name="depr_entry_org_period_idx"
            ),
            models.Index(fields=("organization", "asset"), name="depr_entry_org_asset_idx"),
        ]

    def clean(self):
        super().clean()
        if self.asset_id and self.schedule_id and self.schedule.asset_id != self.asset_id:
            raise ValidationError({"schedule": "Schedule must belong to the entry asset."})
        if self.schedule_id and self.closing_book_value < self.schedule.residual_value:
            raise ValidationError(
                {"closing_book_value": "Closing book value cannot fall below residual value."}
            )
        if self.organization_id:
            for field in ("asset", "schedule", "accounting_period"):
                related = getattr(self, field, None)
                if related and related.organization_id != self.organization_id:
                    raise ValidationError({field: "All entry records must share an organization."})

    def __str__(self):
        period = self.accounting_period
        return f"{self.asset.asset_tag} {period.year}-{period.month:02d}"
