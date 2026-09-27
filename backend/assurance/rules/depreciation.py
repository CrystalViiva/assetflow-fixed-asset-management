from decimal import Decimal

from assets.models import AssetStatus
from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding
from depreciation.models import ScheduleStatus
from depreciation.services.engine import money


def evaluate(asset, context, run, as_of):
    schedule = context.schedules.get(asset.pk)
    entries_total = money(context.entry_totals.get(asset.pk, Decimal("0.00")))
    findings = []
    if (
        asset.status == AssetStatus.ACTIVE
        and asset.capitalization_date
        and asset.useful_life_months
        and schedule is None
    ):
        findings.append(
            make_finding(
                asset,
                FindingType.DEPRECIATION_EXCEPTION,
                FindingSeverity.HIGH,
                FindingSource.DEPRECIATION,
                "Depreciation schedule for active depreciable asset",
                "No schedule",
                "The active capitalized asset has no depreciation schedule.",
            )
        )
    if schedule is not None:
        changed = []
        for field, asset_field in (
            ("capitalized_cost", "purchase_cost"),
            ("residual_value", "residual_value"),
            ("useful_life_months", "useful_life_months"),
            ("method", "depreciation_method"),
        ):
            if getattr(schedule, field) != getattr(asset, asset_field):
                changed.append(field)
        if changed:
            findings.append(
                make_finding(
                    asset,
                    FindingType.DEPRECIATION_EXCEPTION,
                    FindingSeverity.HIGH,
                    FindingSource.DEPRECIATION,
                    "Schedule assumptions agree with current asset basis",
                    ", ".join(changed),
                    "The stored depreciation schedule assumptions differ from the asset master.",
                )
            )
        posted_count = context.schedule_entry_counts.get(asset.pk, 0)
        expected_status = (
            ScheduleStatus.COMPLETE
            if posted_count >= schedule.useful_life_months
            else ScheduleStatus.ACTIVE
        )
        if schedule.status != expected_status:
            findings.append(
                make_finding(
                    asset,
                    FindingType.DEPRECIATION_EXCEPTION,
                    FindingSeverity.MEDIUM,
                    FindingSource.DEPRECIATION,
                    expected_status,
                    schedule.status,
                    "Depreciation schedule status does not agree with posted useful-life periods.",
                )
            )
    if entries_total != money(asset.accumulated_depreciation) and (
        schedule is not None or entries_total or asset.accumulated_depreciation
    ):
        findings.append(
            make_finding(
                asset,
                FindingType.DEPRECIATION_EXCEPTION,
                FindingSeverity.CRITICAL,
                FindingSource.DEPRECIATION,
                entries_total,
                money(asset.accumulated_depreciation),
                "Asset accumulated depreciation differs from the sum of posted entries.",
            )
        )
    if schedule is not None and money(asset.accumulated_depreciation) > money(
        schedule.depreciable_base
    ):
        findings.append(
            make_finding(
                asset,
                FindingType.DEPRECIATION_EXCEPTION,
                FindingSeverity.CRITICAL,
                FindingSource.DEPRECIATION,
                f"At most {money(schedule.depreciable_base)} accumulated depreciation",
                money(asset.accumulated_depreciation),
                "Accumulated depreciation exceeds the schedule's depreciable base.",
            )
        )
    completed_disposals = [
        disposal
        for disposal in context.disposals.get(asset.pk, [])
        if disposal.status == "COMPLETED"
    ]
    latest_entry = context.entry_last_posted.get(asset.pk)
    if (
        asset.status == AssetStatus.DISPOSED
        and completed_disposals
        and latest_entry
        and latest_entry > completed_disposals[0].completed_at
    ):
        findings.append(
            make_finding(
                asset,
                FindingType.DEPRECIATION_EXCEPTION,
                FindingSeverity.CRITICAL,
                FindingSource.DEPRECIATION,
                "No depreciation posted after disposal completion "
                f"{completed_disposals[0].completed_at.isoformat()}",
                latest_entry.isoformat(),
                "A depreciation entry was posted after the completed disposal.",
            )
        )
    return findings
