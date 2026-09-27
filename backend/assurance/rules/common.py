from dataclasses import dataclass

from assurance.models import FindingSeverity, FindingSource, FindingType


@dataclass(frozen=True)
class FindingCandidate:
    asset_id: object
    verification_id: object
    identity_key: str
    finding_type: str
    severity: str
    source: str
    expected_value: str
    observed_value: str
    description: str


def make_finding(
    asset,
    finding_type,
    severity,
    source,
    expected_value,
    observed_value,
    description,
    *,
    verification=None,
):
    identity_key = f"asset:{asset.pk}" if asset is not None else f"physical:{verification.pk}"
    return FindingCandidate(
        asset_id=asset.pk if asset is not None else None,
        verification_id=verification.pk if verification is not None else None,
        identity_key=identity_key,
        finding_type=FindingType(finding_type),
        severity=FindingSeverity(severity),
        source=FindingSource(source),
        expected_value=str(expected_value or ""),
        observed_value=str(observed_value or ""),
        description=description,
    )


def relation_label(value):
    if value is None:
        return "UNASSIGNED"
    return str(value)
