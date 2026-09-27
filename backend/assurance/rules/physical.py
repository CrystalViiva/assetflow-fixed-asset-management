from assurance.models import FindingSeverity, FindingSource, FindingType
from assurance.rules.common import make_finding


def evaluate(asset, context, run, as_of):
    findings = []
    observation = context.latest_verification.get(asset.pk)
    if (
        run.verification_campaign_id
        and asset.pk in context.campaign_expected_asset_ids
        and observation is None
    ):
        findings.append(
            make_finding(
                asset,
                FindingType.MISSING_PHYSICAL_VERIFICATION,
                FindingSeverity.MEDIUM,
                FindingSource.PHYSICAL_VERIFICATION,
                f"verification campaign {run.verification_campaign_id}",
                "No qualifying verification record",
                "The asset was in the selected campaign population but has no verification record.",
            )
        )
        return findings
    if observation is None:
        return findings

    tag = observation.observed_asset_tag.strip()
    if tag != asset.asset_tag:
        findings.append(
            make_finding(
                asset,
                FindingType.TAG_MISMATCH,
                FindingSeverity.HIGH,
                FindingSource.PHYSICAL_VERIFICATION,
                asset.asset_tag,
                tag or "MISSING",
                "The observed asset tag is missing or differs from the registered tag.",
                verification=observation,
            )
        )
    if asset.pk in context.duplicate_tag_assets:
        findings.append(
            make_finding(
                asset,
                FindingType.DUPLICATE_TAG,
                FindingSeverity.CRITICAL,
                FindingSource.PHYSICAL_VERIFICATION,
                "One occurrence of the observed tag in this campaign",
                tag,
                "The observed tag is attached to multiple verification observations.",
                verification=observation,
            )
        )
    if observation.pk in context.asset_not_found_verification_ids:
        findings.append(
            make_finding(
                asset,
                FindingType.ASSET_NOT_FOUND,
                FindingSeverity.HIGH,
                FindingSource.PHYSICAL_VERIFICATION,
                "Asset physically present",
                "Not found during verification",
                "The selected campaign records this expected asset as not found.",
                verification=observation,
            )
        )
    return findings


def evaluate_unregistered(context):
    findings = []
    for observation in context.unregistered_verifications:
        findings.append(
            make_finding(
                None,
                FindingType.UNREGISTERED_ASSET,
                FindingSeverity.HIGH,
                FindingSource.PHYSICAL_VERIFICATION,
                "Registered asset record",
                observation.observed_asset_tag
                or observation.observed_description
                or "Unidentified",
                "A physical item was observed without a matching registered asset.",
                verification=observation,
            )
        )
        if observation.pk in context.duplicate_tag_verifications:
            findings.append(
                make_finding(
                    None,
                    FindingType.DUPLICATE_TAG,
                    FindingSeverity.CRITICAL,
                    FindingSource.PHYSICAL_VERIFICATION,
                    "Unique observed tag",
                    observation.observed_asset_tag,
                    "The unregistered item's observed tag is duplicated in the campaign.",
                    verification=observation,
                )
            )
        if observation.pk in context.asset_not_found_verification_ids:
            findings.append(
                make_finding(
                    None,
                    FindingType.ASSET_NOT_FOUND,
                    FindingSeverity.HIGH,
                    FindingSource.PHYSICAL_VERIFICATION,
                    "Registered asset record",
                    "Not found",
                    "The physical verification exception refers to a missing registered asset.",
                    verification=observation,
                )
            )
    return findings
