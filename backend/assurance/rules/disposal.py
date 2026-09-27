from assets.models import AssetStatus
from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding
from disposals.models import DisposalStatus


def evaluate(asset, context, run, as_of):
    disposals = context.disposals.get(asset.pk, [])
    completed = [d for d in disposals if d.status == DisposalStatus.COMPLETED]
    if completed and asset.status != AssetStatus.DISPOSED:
        expected = AssetStatus.DISPOSED
        observed = asset.status
        description = "A completed disposal exists but the asset lifecycle is not DISPOSED."
    elif asset.status == AssetStatus.DISPOSED and not completed:
        expected = "Completed disposal record"
        observed = asset.status
        description = "The asset is DISPOSED without a completed disposal record."
    elif completed:
        disposal = completed[0]
        mismatches = []
        expected_cost = str(disposal.capitalized_cost_at_disposal)
        expected_accumulated = str(disposal.accumulated_depreciation_at_disposal)
        if disposal.capitalized_cost_at_disposal != asset.purchase_cost:
            mismatches.append("capitalized cost snapshot")
        if disposal.accumulated_depreciation_at_disposal != asset.accumulated_depreciation:
            mismatches.append("accumulated depreciation snapshot")
        if mismatches:
            expected = f"cost={expected_cost}; accumulated={expected_accumulated}"
            observed = f"cost={asset.purchase_cost}; accumulated={asset.accumulated_depreciation}"
            description = (
                "Completed disposal accounting snapshots differ from the asset's retained "
                f"accounting balances: {', '.join(mismatches)}."
            )
        else:
            return []
    else:
        return []
    return [
        make_finding(
            asset,
            FindingType.DISPOSAL_STATUS_MISMATCH,
            FindingSeverity.CRITICAL,
            FindingSource.DISPOSAL,
            expected,
            observed,
            description,
        )
    ]
