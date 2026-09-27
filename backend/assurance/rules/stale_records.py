from datetime import timedelta

from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding


def evaluate(asset, context, run, as_of):
    threshold = as_of - timedelta(days=run.stale_after_days)
    if asset.updated_at >= threshold:
        return []
    return [
        make_finding(
            asset,
            FindingType.STALE_RECORD,
            FindingSeverity.LOW,
            FindingSource.ASSET_MASTER,
            f"Asset updated on or after {threshold.isoformat()}",
            asset.updated_at.isoformat(),
            f"The asset master has not been updated within the run threshold of "
            f"{run.stale_after_days} days.",
        )
    ]
