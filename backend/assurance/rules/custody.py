from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding, relation_label


def evaluate(asset, context, run, as_of):
    observation = context.latest_verification.get(asset.pk)
    if observation is None:
        return []
    assignment = context.assignments.get(asset.pk)
    assigned_to = assignment.assigned_to if assignment else None
    if (assigned_to.pk if assigned_to else None) == observation.observed_custodian_id:
        return []
    return [
        make_finding(
            asset,
            FindingType.CUSTODY_MISMATCH,
            FindingSeverity.HIGH,
            FindingSource.ASSIGNMENT,
            relation_label(assigned_to),
            relation_label(observation.observed_custodian),
            "Observed custody differs from the current active asset assignment.",
            verification=observation,
        )
    ]
