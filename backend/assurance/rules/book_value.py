from assets.models import AssetStatus
from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding
from depreciation.services.engine import money


def evaluate(asset, context, run, as_of):
    if not asset.capitalization_date and asset.status != AssetStatus.DISPOSED:
        return []
    schedule = context.schedules.get(asset.pk)
    cost = money(schedule.capitalized_cost if schedule else asset.purchase_cost)
    residual = money(schedule.residual_value if schedule else asset.residual_value)
    accumulated = money(asset.accumulated_depreciation)
    expected = money(cost - accumulated)
    if expected < residual:
        expected = residual
    observed = money(asset.current_book_value)
    if observed == expected:
        return []
    return [
        make_finding(
            asset,
            FindingType.BOOK_VALUE_EXCEPTION,
            FindingSeverity.CRITICAL,
            FindingSource.DEPRECIATION,
            expected,
            observed,
            "Current book value differs from capitalized cost less accumulated depreciation, "
            "subject to the recorded residual value.",
        )
    ]
