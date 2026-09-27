from assets.models import AssetCondition
from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding
from verification.models import PhysicalCondition


def evaluate(asset, context, run, as_of):
    observation = context.latest_verification.get(asset.pk)
    if observation is None:
        return []
    expected = asset.condition
    observed = observation.observed_condition
    if (
        expected == AssetCondition.UNKNOWN
        or observed == PhysicalCondition.UNKNOWN
        or expected == observed
    ):
        return []
    severity = (
        FindingSeverity.CRITICAL
        if observed == PhysicalCondition.CRITICAL
        else FindingSeverity.HIGH
        if observed == PhysicalCondition.DAMAGED
        else FindingSeverity.MEDIUM
    )
    return [
        make_finding(
            asset,
            FindingType.CONDITION_EXCEPTION,
            severity,
            FindingSource.PHYSICAL_VERIFICATION,
            expected,
            observed,
            "The observed condition differs from the known registered asset condition.",
            verification=observation,
        )
    ]
