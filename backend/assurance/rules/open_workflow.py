from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding


def evaluate(asset, context, run, as_of):
    transfers = context.transfers.get(asset.pk, [])
    work_orders = context.work_orders.get(asset.pk, [])
    disposals = [
        item
        for item in context.disposals.get(asset.pk, [])
        if item.status in {"DRAFT", "PENDING_APPROVAL", "APPROVED"}
    ]
    if not (transfers or work_orders or disposals):
        return []
    workflow_rows = [
        *(f"transfer:{row.status}" for row in transfers),
        *(f"maintenance:{row.status}" for row in work_orders),
        *(f"disposal:{row.status}" for row in disposals),
    ]
    source = (
        FindingSource.DISPOSAL
        if disposals
        else FindingSource.TRANSFER
        if transfers
        else FindingSource.MAINTENANCE
    )
    return [
        make_finding(
            asset,
            FindingType.OPEN_WORKFLOW,
            FindingSeverity.MEDIUM,
            source,
            "No unresolved operational workflow",
            ", ".join(sorted(workflow_rows)),
            "The asset has an unresolved transfer, maintenance, or disposal workflow.",
        )
    ]
