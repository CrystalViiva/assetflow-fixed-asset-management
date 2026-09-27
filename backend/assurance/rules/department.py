from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding, relation_label


def evaluate(asset, context, run, as_of):
    observation = context.latest_verification.get(asset.pk)
    if observation is None or asset.department_id == observation.observed_department_id:
        return []
    return [
        make_finding(
            asset,
            FindingType.DEPARTMENT_MISMATCH,
            FindingSeverity.HIGH,
            FindingSource.PHYSICAL_VERIFICATION,
            relation_label(asset.department),
            relation_label(observation.observed_department),
            "The latest relevant physical observation assigns the asset to a different department.",
            verification=observation,
        )
    ]
