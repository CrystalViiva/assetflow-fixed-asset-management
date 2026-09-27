from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding, relation_label


def evaluate(asset, context, run, as_of):
    observation = context.latest_verification.get(asset.pk)
    if observation is None:
        return []
    expected = relation_label(asset.location)
    observed = relation_label(observation.observed_location)
    if asset.location_id == observation.observed_location_id:
        return []
    return [
        make_finding(
            asset,
            FindingType.LOCATION_MISMATCH,
            FindingSeverity.HIGH,
            FindingSource.PHYSICAL_VERIFICATION,
            expected,
            observed,
            "The latest relevant physical observation places the asset at a different location.",
            verification=observation,
        )
    ]
