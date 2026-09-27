from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding


def evaluate(asset, context, run, as_of):
    observation = context.latest_verification.get(asset.pk)
    if observation is None:
        return []
    if observation.pk not in context.severe_exception_verification_ids:
        return []
    if observation.pk in context.verification_evidence_ids:
        return []
    return [
        make_finding(
            asset,
            FindingType.MISSING_EVIDENCE,
            FindingSeverity.HIGH,
            FindingSource.EVIDENCE,
            "At least one evidence metadata record for a HIGH/CRITICAL exception",
            "No evidence metadata record",
            "A high-severity physical verification exception has no associated evidence metadata.",
        )
    ]


def evaluate_unregistered(context):
    return [
        make_finding(
            None,
            FindingType.MISSING_EVIDENCE,
            FindingSeverity.HIGH,
            FindingSource.EVIDENCE,
            "At least one evidence metadata record for a HIGH/CRITICAL exception",
            "No evidence metadata record",
            "A high-severity physical verification exception has no associated evidence metadata.",
            verification=observation,
        )
        for observation in context.unregistered_verifications
        if observation.pk in context.severe_exception_verification_ids
        and observation.pk not in context.verification_evidence_ids
    ]
