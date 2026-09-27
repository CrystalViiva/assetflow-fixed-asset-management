from assets.models import AssetStatus
from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding

INACTIVE_STATES = {
    AssetStatus.DRAFT,
    AssetStatus.PENDING_CAPITALIZATION,
    AssetStatus.DISPOSED,
}


def evaluate(asset, context, run, as_of):
    active_assignment = asset.pk in context.assignments
    active_work = bool(context.work_orders.get(asset.pk))
    active_transfer = bool(context.transfers.get(asset.pk))
    if asset.status not in INACTIVE_STATES or not (
        active_assignment or active_work or active_transfer
    ):
        return []
    workflows = []
    if active_assignment:
        workflows.append("active assignment")
    if active_work:
        workflows.append("active maintenance work order")
    if active_transfer:
        workflows.append("pending transfer")
    severity = (
        FindingSeverity.CRITICAL if asset.status == AssetStatus.DISPOSED else FindingSeverity.HIGH
    )
    source = (
        FindingSource.ASSIGNMENT
        if active_assignment
        else FindingSource.MAINTENANCE
        if active_work
        else FindingSource.TRANSFER
    )
    return [
        make_finding(
            asset,
            FindingType.LIFECYCLE_MISMATCH,
            severity,
            source,
            f"No active operational workflow for {asset.status}",
            ", ".join(workflows),
            "The asset lifecycle conflicts with one or more active operational workflows.",
        )
    ]
