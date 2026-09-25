"""Transactional schedule, period, posting, and period-close operations."""

import calendar
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from assets.models import Asset, AssetStatus, DepreciationMethod
from audit.services import record_event
from depreciation.models import (
    AccountingPeriod,
    DepreciationEntry,
    DepreciationSchedule,
    PeriodStatus,
    ScheduleStatus,
)
from depreciation.services.engine import (
    calculate_period_amount,
    money,
    straight_line_periodic_amount,
)


def _organization(actor):
    if not getattr(actor, "organization_id", None):
        raise ValidationError(
            {"organization": "The authenticated user must belong to an organization."}
        )
    return actor.organization


def _month_offset(value, offset):
    absolute = value.year * 12 + value.month - 1 + offset
    year, month0 = divmod(absolute, 12)
    month = month0 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _schedule_end(start, months):
    final_month = _month_offset(start.replace(day=1), months - 1)
    return date(
        final_month.year,
        final_month.month,
        calendar.monthrange(final_month.year, final_month.month)[1],
    )


def create_accounting_period(*, actor, year, month, ip_address=None):
    organization = _organization(actor)
    if not 1 <= int(month) <= 12 or not 1900 <= int(year) <= 9999:
        raise ValidationError({"period": "Provide a valid calendar year and month."})
    with transaction.atomic():
        try:
            period = AccountingPeriod.objects.create(
                organization=organization, year=year, month=month
            )
        except IntegrityError as exc:
            raise ValidationError({"period": "This accounting period already exists."}) from exc
        record_event(
            organization=organization,
            user=actor,
            action="ACCOUNTING_PERIOD_CREATED",
            entity_type="ACCOUNTING_PERIOD",
            entity_id=period.pk,
            ip_address=ip_address,
            changes={"status": {"from": None, "to": period.status}},
            metadata={"year": period.year, "month": period.month},
        )
    return period


def generate_depreciation_schedule(*, asset_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        try:
            asset = Asset.objects.select_for_update(of=("self",)).get(
                pk=asset_id, organization=organization
            )
        except Asset.DoesNotExist as exc:
            raise ValidationError(
                {"asset": "The asset was not found in your organization."}
            ) from exc
        if asset.status != AssetStatus.ACTIVE:
            raise ValidationError({"asset": "Only capitalized active assets can be scheduled."})
        if asset.capitalization_date is None:
            raise ValidationError({"capitalization_date": "The asset must be capitalized."})
        if asset.available_for_use_date is None:
            raise ValidationError(
                {"available_for_use_date": "An available-for-use date is required."}
            )
        if asset.available_for_use_date < asset.capitalization_date:
            raise ValidationError(
                {"available_for_use_date": "Available-for-use cannot precede capitalization."}
            )
        if asset.depreciation_method != DepreciationMethod.SLM:
            raise ValidationError(
                {"method": f"{asset.depreciation_method} calculation is not implemented."}
            )
        if asset.useful_life_months is None or asset.useful_life_months <= 0:
            raise ValidationError({"useful_life_months": "Useful life must be positive."})
        cost = money(asset.purchase_cost)
        residual = money(asset.residual_value)
        if cost <= 0 or residual > cost:
            raise ValidationError(
                {"purchase_cost": "A valid capitalized cost and residual value are required."}
            )
        if asset.current_book_value != cost or asset.accumulated_depreciation != Decimal("0.00"):
            raise ValidationError(
                {"asset": "A schedule requires an asset with its initial capitalized balance."}
            )
        if DepreciationSchedule.objects.filter(asset=asset).exists():
            raise ValidationError(
                {"schedule": "A depreciation schedule already exists for this asset."}
            )

        periodic = straight_line_periodic_amount(
            capitalized_cost=cost,
            residual_value=residual,
            useful_life_months=asset.useful_life_months,
        )
        schedule = DepreciationSchedule.objects.create(
            organization=organization,
            asset=asset,
            method=asset.depreciation_method,
            capitalized_cost=cost,
            depreciable_base=money(cost - residual),
            residual_value=residual,
            useful_life_months=asset.useful_life_months,
            start_date=asset.available_for_use_date,
            end_date=_schedule_end(asset.available_for_use_date, asset.useful_life_months),
            periodic_depreciation=periodic,
        )
        record_event(
            organization=organization,
            user=actor,
            action="DEPRECIATION_SCHEDULE_CREATED",
            entity_type="DEPRECIATION_SCHEDULE",
            entity_id=schedule.pk,
            ip_address=ip_address,
            changes={"status": {"from": None, "to": schedule.status}},
            metadata={
                "asset_id": str(asset.pk),
                "method": schedule.method,
                "depreciable_amount": str(cost - residual),
                "useful_life_months": schedule.useful_life_months,
                "start_date": schedule.start_date.isoformat(),
            },
        )
    return schedule


def post_depreciation(*, asset_id, period_id, actor, ip_address=None):
    """Post the next scheduled calendar month with ledger, balance, and audit atomicity."""
    organization = _organization(actor)
    try:
        with transaction.atomic():
            try:
                period = AccountingPeriod.objects.select_for_update(of=("self",)).get(
                    pk=period_id, organization=organization
                )
            except AccountingPeriod.DoesNotExist as exc:
                raise ValidationError(
                    {"period": "The accounting period was not found in your organization."}
                ) from exc
            if period.status != PeriodStatus.OPEN:
                raise ValidationError(
                    {"period": "Depreciation can only be posted into an open period."}
                )
            try:
                asset = Asset.objects.select_for_update(of=("self",)).get(
                    pk=asset_id, organization=organization
                )
            except Asset.DoesNotExist as exc:
                raise ValidationError(
                    {"asset": "The asset was not found in your organization."}
                ) from exc
            if asset.status != AssetStatus.ACTIVE:
                raise ValidationError({"asset": "Only active assets may receive depreciation."})
            try:
                schedule = DepreciationSchedule.objects.select_for_update(of=("self",)).get(
                    asset=asset, organization=organization
                )
            except DepreciationSchedule.DoesNotExist as exc:
                raise ValidationError(
                    {"schedule": "Generate a depreciation schedule first."}
                ) from exc

            entries = DepreciationEntry.objects.filter(schedule=schedule)
            posted_count = entries.count()
            expected = _month_offset(schedule.start_date.replace(day=1), posted_count)
            if period.first_day != expected:
                raise ValidationError(
                    {"period": f"Post periods sequentially; next period is {expected:%Y-%m}."}
                )
            if posted_count >= schedule.useful_life_months:
                raise ValidationError({"schedule": "The depreciation schedule is complete."})

            prior = entries.order_by(
                "-accounting_period__year", "-accounting_period__month"
            ).first()
            opening = money(asset.current_book_value)
            prior_accumulated = money(prior.accumulated_depreciation if prior else Decimal("0.00"))
            if prior and opening != money(prior.closing_book_value):
                raise ValidationError(
                    {"asset": "Asset book value does not agree with the prior ledger entry."}
                )
            if prior and money(asset.accumulated_depreciation) != prior_accumulated:
                raise ValidationError(
                    {
                        "asset": (
                            "Accumulated depreciation does not agree with the prior ledger entry."
                        )
                    }
                )
            if not prior and (
                opening != money(schedule.capitalized_cost)
                or money(asset.accumulated_depreciation) != Decimal("0.00")
            ):
                raise ValidationError(
                    {"asset": "Initial book value does not agree with the schedule basis."}
                )
            amount = calculate_period_amount(
                method=schedule.method,
                opening_book_value=opening,
                residual_value=schedule.residual_value,
                depreciable_base=schedule.depreciable_base,
                periodic_depreciation=schedule.periodic_depreciation,
                accumulated_depreciation=prior_accumulated,
            )
            closing = money(opening - amount)
            accumulated = money(prior_accumulated + amount)
            if closing < schedule.residual_value:
                raise ValidationError(
                    {"asset": "Depreciation cannot reduce carrying amount below residual value."}
                )

            entry = DepreciationEntry.objects.create(
                organization=organization,
                asset=asset,
                schedule=schedule,
                accounting_period=period,
                opening_book_value=opening,
                depreciation_amount=amount,
                accumulated_depreciation=accumulated,
                closing_book_value=closing,
                created_by=actor,
            )
            asset.accumulated_depreciation = accumulated
            asset.current_book_value = closing
            asset.updated_by = actor
            asset.save(
                update_fields=(
                    "accumulated_depreciation",
                    "current_book_value",
                    "updated_by",
                    "updated_at",
                )
            )
            changes = {
                "current_book_value": {"from": str(opening), "to": str(closing)},
                "accumulated_depreciation": {
                    "from": str(prior_accumulated),
                    "to": str(accumulated),
                },
                "depreciation_amount": {"from": None, "to": str(amount)},
            }
            record_event(
                organization=organization,
                user=actor,
                action="DEPRECIATION_POSTED",
                entity_type="DEPRECIATION_ENTRY",
                entity_id=entry.pk,
                ip_address=ip_address,
                changes=changes,
                metadata={"asset_id": str(asset.pk), "period": period.first_day.isoformat()},
            )
            if posted_count + 1 == schedule.useful_life_months:
                schedule.status = ScheduleStatus.COMPLETE
                schedule.save(update_fields=("status", "updated_at"))
    except IntegrityError as exc:
        raise ValidationError(
            {"period": "Depreciation has already been posted for this asset and period."}
        ) from exc
    return entry


def close_accounting_period(*, period_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        try:
            period = AccountingPeriod.objects.select_for_update(of=("self",)).get(
                pk=period_id, organization=organization
            )
        except AccountingPeriod.DoesNotExist as exc:
            raise ValidationError(
                {"period": "The accounting period was not found in your organization."}
            ) from exc
        if period.status != PeriodStatus.OPEN:
            raise ValidationError({"status": "Only open accounting periods can be closed."})
        before = period.status
        period.status = PeriodStatus.CLOSED
        period.closed_at = timezone.now()
        period.closed_by = actor
        period.full_clean()
        period.save(update_fields=("status", "closed_at", "closed_by", "updated_at"))
        record_event(
            organization=organization,
            user=actor,
            action="ACCOUNTING_PERIOD_CLOSED",
            entity_type="ACCOUNTING_PERIOD",
            entity_id=period.pk,
            ip_address=ip_address,
            changes={"status": {"from": before, "to": period.status}},
            metadata={"year": period.year, "month": period.month},
        )
    return period
