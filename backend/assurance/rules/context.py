"""Organization-scoped snapshots used by deterministic controls."""

from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import Count, Sum

from depreciation.models import DepreciationEntry, DepreciationSchedule
from disposals.models import Disposal
from maintenance.models import WorkOrder
from transfers.models import AssetAssignment, AssetTransfer
from verification.models import (
    ExceptionSeverity,
    ExceptionType,
    PhysicalVerification,
    VerificationEvidence,
    VerificationException,
)
from verification.selectors import expected_assets


@dataclass
class EvaluationContext:
    latest_verification: dict = field(default_factory=dict)
    verifications: list = field(default_factory=list)
    unregistered_verifications: list = field(default_factory=list)
    duplicate_tag_assets: set = field(default_factory=set)
    duplicate_tag_verifications: set = field(default_factory=set)
    campaign_expected_asset_ids: set = field(default_factory=set)
    assignments: dict = field(default_factory=dict)
    work_orders: dict = field(default_factory=lambda: defaultdict(list))
    transfers: dict = field(default_factory=lambda: defaultdict(list))
    disposals: dict = field(default_factory=lambda: defaultdict(list))
    schedules: dict = field(default_factory=dict)
    schedule_entry_counts: dict = field(default_factory=dict)
    entry_totals: dict = field(default_factory=dict)
    entry_last_posted: dict = field(default_factory=dict)
    verification_evidence_ids: set = field(default_factory=set)
    severe_exception_verification_ids: set = field(default_factory=set)
    asset_not_found_verification_ids: set = field(default_factory=set)
    exceptions_by_verification: dict = field(default_factory=lambda: defaultdict(list))


def build_context(*, run, assets):
    asset_ids = [asset.pk for asset in assets]
    context = EvaluationContext()
    organization_id = run.organization_id
    if run.verification_campaign_id:
        context.campaign_expected_asset_ids = set(
            expected_assets(run.verification_campaign).values_list("pk", flat=True)
        )

    verifications = PhysicalVerification.objects.filter(
        organization_id=organization_id,
        verified_at__lte=run.started_at,
    ).select_related("observed_location", "observed_department", "observed_custodian")
    if run.verification_campaign_id:
        verifications = verifications.filter(campaign_id=run.verification_campaign_id)
    verifications = verifications.order_by("asset_id", "-verified_at", "-created_at")
    context.verifications = list(verifications)
    for verification in verifications:
        if verification.asset_id in asset_ids:
            context.latest_verification.setdefault(verification.asset_id, verification)
        elif verification.asset_id is None and run.verification_campaign_id:
            context.unregistered_verifications.append(verification)
    duplicate_scope = (
        context.verifications
        if run.verification_campaign_id
        else list(context.latest_verification.values())
    )
    all_tags = defaultdict(list)
    for verification in duplicate_scope:
        normalized_tag = verification.observed_asset_tag.strip().casefold()
        if normalized_tag:
            all_tags[(verification.campaign_id, normalized_tag)].append(verification)
    context.duplicate_tag_assets = {
        verification.asset_id
        for records in all_tags.values()
        if len(records) > 1
        for verification in records
        if verification.asset_id
    }
    context.duplicate_tag_verifications = {
        verification.pk
        for records in all_tags.values()
        if len(records) > 1
        for verification in records
    }

    for assignment in AssetAssignment.objects.filter(
        organization_id=organization_id, asset_id__in=asset_ids, returned_at__isnull=True
    ).select_related("assigned_to"):
        context.assignments[assignment.asset_id] = assignment

    for order in WorkOrder.objects.filter(
        organization_id=organization_id,
        asset_id__in=asset_ids,
        status__in=("OPEN", "ASSIGNED", "IN_PROGRESS"),
    ):
        context.work_orders[order.asset_id].append(order)

    for transfer in AssetTransfer.objects.filter(
        organization_id=organization_id,
        asset_id__in=asset_ids,
        status__in=("REQUESTED", "APPROVED"),
    ):
        context.transfers[transfer.asset_id].append(transfer)

    for disposal in Disposal.objects.filter(
        organization_id=organization_id,
        asset_id__in=asset_ids,
        status__in=("DRAFT", "PENDING_APPROVAL", "APPROVED", "COMPLETED"),
    ):
        context.disposals[disposal.asset_id].append(disposal)

    context.schedules = {
        schedule.asset_id: schedule
        for schedule in DepreciationSchedule.objects.filter(
            organization_id=organization_id, asset_id__in=asset_ids
        ).annotate(_assurance_entry_count=Count("entries"))
    }
    context.schedule_entry_counts = {
        schedule.asset_id: schedule._assurance_entry_count
        for schedule in context.schedules.values()
    }
    entry_rows = (
        DepreciationEntry.objects.filter(organization_id=organization_id, asset_id__in=asset_ids)
        .values("asset_id")
        .annotate(total=Sum("depreciation_amount"))
    )
    context.entry_totals = {row["asset_id"]: row["total"] for row in entry_rows}
    for asset_id, posted_at in (
        DepreciationEntry.objects.filter(organization_id=organization_id, asset_id__in=asset_ids)
        .order_by("asset_id", "-posted_at")
        .values_list("asset_id", "posted_at")
    ):
        context.entry_last_posted.setdefault(asset_id, posted_at)
    used_verification_ids = [v.pk for v in context.verifications]
    if used_verification_ids:
        exceptions = list(
            VerificationException.objects.filter(
                organization_id=organization_id,
                verification_id__in=used_verification_ids,
            ).only("verification_id", "exception_type", "severity")
        )
        for exception in exceptions:
            context.exceptions_by_verification[exception.verification_id].append(exception)
            if exception.severity in (ExceptionSeverity.HIGH, ExceptionSeverity.CRITICAL):
                context.severe_exception_verification_ids.add(exception.verification_id)
        # Keep the exception type available to the physical rules without issuing one query per row.
        context.asset_not_found_verification_ids = set(
            exception.verification_id
            for exception in exceptions
            if exception.exception_type == ExceptionType.ASSET_NOT_FOUND
        )
        context.verification_evidence_ids = set(
            VerificationEvidence.objects.filter(
                organization_id=organization_id,
                verification_id__in=used_verification_ids,
            ).values_list("verification_id", flat=True)
        )
        exception_evidence = VerificationEvidence.objects.filter(
            organization_id=organization_id,
            verification__in=used_verification_ids,
            exception_id__isnull=False,
        ).values_list("verification_id", flat=True)
        context.verification_evidence_ids.update(exception_evidence)
    return context
