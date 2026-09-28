"""Transactional assurance-run orchestration and finding deduplication."""

from functools import partial

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from assets.models import Asset
from assurance.models import (
    ACTIVE_FINDING_STATUSES,
    AssuranceFinding,
    AssuranceFindingOccurrence,
    AssuranceRun,
    AssuranceRunStatus,
    AssuranceRunType,
    FindingSeverity,
    FindingStatus,
)
from assurance.rules import RULES_BY_RUN_TYPE
from assurance.rules.context import build_context
from assurance.services.audit import audit
from verification.models import CampaignStatus, VerificationCampaign
from verification.selectors import expected_assets

SEVERITY_RANK = {
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}


def _organization(actor):
    if not getattr(actor, "organization_id", None):
        raise ValidationError({"organization": "The user must belong to an organization."})
    return actor.organization


def _locked_run(run_id, organization):
    try:
        return AssuranceRun.objects.select_for_update(of=("self",)).get(
            pk=run_id, organization=organization
        )
    except AssuranceRun.DoesNotExist as exc:
        raise ValidationError({"run": "Assurance run was not found in your organization."}) from exc


def create_run(
    *,
    actor,
    run_type,
    verification_campaign=None,
    stale_after_days=365,
    ip_address=None,
):
    organization = _organization(actor)
    if verification_campaign and verification_campaign.organization_id != organization.pk:
        raise ValidationError({"verification_campaign": "Campaign is outside your organization."})
    run = AssuranceRun(
        organization=organization,
        run_type=run_type,
        verification_campaign=verification_campaign,
        stale_after_days=stale_after_days,
        started_by=actor,
    )
    run.full_clean()
    with transaction.atomic():
        if verification_campaign:
            try:
                locked_campaign = VerificationCampaign.objects.select_for_update().get(
                    pk=verification_campaign.pk,
                    organization_id=organization.pk,
                )
            except VerificationCampaign.DoesNotExist as exc:
                raise ValidationError(
                    {"verification_campaign": "Campaign was not found in your organization."}
                ) from exc
            if locked_campaign.status != CampaignStatus.COMPLETED:
                raise ValidationError(
                    {"verification_campaign": "Assurance runs require a completed campaign."}
                )
            run.verification_campaign = locked_campaign
        run.save()
        audit(
            organization=organization,
            actor=actor,
            action="ASSURANCE_RUN_CREATED",
            entity_type="ASSURANCE_RUN",
            entity_id=run.pk,
            metadata={
                "run_type": run.run_type,
                "verification_campaign_id": str(run.verification_campaign_id or ""),
                "stale_after_days": run.stale_after_days,
            },
            ip_address=ip_address,
        )
    return run


def _asset_population(run):
    """Return the deterministic evaluation population for this durable run.

    The current evaluator consumes the complete scoped population to build cross-asset
    rule context (including duplicate-tag checks), then evaluates it in one transaction.
    A future bounded implementation must preserve a run-level snapshot and global
    candidate identity semantics before chunking this queryset.
    """
    assets = Asset.objects.filter(organization_id=run.organization_id)
    if run.run_type == AssuranceRunType.PHYSICAL:
        assets = expected_assets(run.verification_campaign)
    return assets.select_related("department", "location", "depreciation_schedule").order_by("pk")


def _collect_candidates(run, assets):
    context = build_context(run=run, assets=assets)
    candidates = []
    for asset in assets:
        for rule in RULES_BY_RUN_TYPE[run.run_type]:
            candidates.extend(rule(asset, context, run, run.started_at))
    if run.verification_campaign_id and run.run_type != AssuranceRunType.FINANCIAL:
        from assurance.rules import evidence
        from assurance.rules.evidence import evaluate_unregistered as evaluate_unregistered_evidence
        from assurance.rules.physical import evaluate_unregistered as evaluate_unregistered_physical

        candidates.extend(evaluate_unregistered_physical(context))
        if evidence.evaluate in RULES_BY_RUN_TYPE[run.run_type]:
            candidates.extend(evaluate_unregistered_evidence(context))
    return _merge_candidates(candidates)


def _merge_candidates(candidates):
    grouped = {}
    for item in candidates:
        key = (item.identity_key, item.finding_type)
        prior = grouped.get(key)
        if prior is None:
            grouped[key] = item
            continue
        severity = max((prior.severity, item.severity), key=SEVERITY_RANK.get)
        grouped[key] = type(item)(
            asset_id=item.asset_id,
            verification_id=item.verification_id,
            identity_key=item.identity_key,
            finding_type=item.finding_type,
            severity=severity,
            source=prior.source,
            expected_value=" | ".join(
                dict.fromkeys(filter(None, (prior.expected_value, item.expected_value)))
            ),
            observed_value=" | ".join(
                dict.fromkeys(filter(None, (prior.observed_value, item.observed_value)))
            ),
            description=" ".join(dict.fromkeys((prior.description, item.description))),
        )
    return list(grouped.values())


def _add_occurrence(*, finding, run, candidate):
    occurrence = AssuranceFindingOccurrence(
        organization_id=run.organization_id,
        finding=finding,
        assurance_run=run,
        detected_at=run.started_at,
        expected_value=candidate.expected_value,
        observed_value=candidate.observed_value,
        description=candidate.description,
    )
    occurrence.full_clean()
    occurrence.save()
    return occurrence


def _record_candidate(*, run, actor, candidate, ip_address=None):
    finding = (
        AssuranceFinding.objects.select_for_update(of=("self",))
        .filter(
            organization_id=run.organization_id,
            identity_key=candidate.identity_key,
            finding_type=candidate.finding_type,
            status__in=ACTIVE_FINDING_STATUSES,
        )
        .first()
    )
    if finding is None:
        finding = AssuranceFinding(
            organization_id=run.organization_id,
            assurance_run=run,
            last_detected_run=run,
            asset_id=candidate.asset_id,
            physical_verification_id=candidate.verification_id,
            identity_key=candidate.identity_key,
            finding_type=candidate.finding_type,
            severity=candidate.severity,
            status=FindingStatus.OPEN,
            source=candidate.source,
            expected_value=candidate.expected_value,
            observed_value=candidate.observed_value,
            description=candidate.description,
            occurrence_count=1,
            first_detected_at=run.started_at,
            last_detected_at=run.started_at,
        )
        finding.full_clean()
        try:
            with transaction.atomic():
                finding.save()
        except IntegrityError:
            # A concurrent run may have inserted the same active identity after our read.
            finding = AssuranceFinding.objects.select_for_update(of=("self",)).get(
                organization_id=run.organization_id,
                identity_key=candidate.identity_key,
                finding_type=candidate.finding_type,
                status__in=ACTIVE_FINDING_STATUSES,
            )
        else:
            _add_occurrence(finding=finding, run=run, candidate=candidate)
            audit(
                organization=run.organization,
                actor=actor,
                action="ASSURANCE_FINDING_CREATED",
                entity_type="ASSURANCE_FINDING",
                entity_id=finding.pk,
                metadata={
                    "run_id": str(run.pk),
                    "asset_id": str(finding.asset_id or ""),
                    "finding_type": finding.finding_type,
                },
                ip_address=ip_address,
            )
            return finding

    occurrence_exists = AssuranceFindingOccurrence.objects.filter(
        finding=finding, assurance_run=run
    ).exists()
    before = finding.occurrence_count
    if not occurrence_exists:
        finding.occurrence_count += 1
        _add_occurrence(finding=finding, run=run, candidate=candidate)
    finding.last_detected_at = run.started_at
    finding.last_detected_run = run
    finding.severity = max((finding.severity, candidate.severity), key=SEVERITY_RANK.get)
    finding.expected_value = candidate.expected_value
    finding.observed_value = candidate.observed_value
    finding.description = candidate.description
    finding.save(
        update_fields=(
            "occurrence_count",
            "last_detected_at",
            "last_detected_run",
            "severity",
            "expected_value",
            "observed_value",
            "description",
            "updated_at",
        )
    )
    audit(
        organization=run.organization,
        actor=actor,
        action="ASSURANCE_FINDING_UPDATED",
        entity_type="ASSURANCE_FINDING",
        entity_id=finding.pk,
        changes={"occurrence_count": {"from": before, "to": finding.occurrence_count}},
        metadata={"run_id": str(run.pk)},
        ip_address=ip_address,
    )
    return finding


def _evaluate_locked_run(run_id, organization, actor, ip_address):
    run = _locked_run(run_id, organization)
    if run.status != AssuranceRunStatus.RUNNING:
        raise ValidationError({"status": "Only a running assurance run can be evaluated."})
    assets = list(_asset_population(run).select_for_update(of=("self",)))
    candidates = _collect_candidates(run, assets)
    findings = [
        _record_candidate(run=run, actor=actor, candidate=item, ip_address=ip_address)
        for item in candidates
    ]
    run.status = AssuranceRunStatus.COMPLETED
    run.completed_at = timezone.now()
    run.completed_by = actor
    run.assets_evaluated = len(assets)
    run.findings_generated = len(findings)
    run.findings_open = sum(item.status in ACTIVE_FINDING_STATUSES for item in findings)
    run.findings_resolved = sum(item.status == FindingStatus.RESOLVED for item in findings)
    run.full_clean()
    run.save(
        update_fields=(
            "status",
            "completed_at",
            "completed_by",
            "assets_evaluated",
            "findings_generated",
            "findings_open",
            "findings_resolved",
            "updated_at",
        )
    )
    audit(
        organization=organization,
        actor=actor,
        action="ASSURANCE_RUN_COMPLETED",
        entity_type="ASSURANCE_RUN",
        entity_id=run.pk,
        changes={
            "status": {"from": AssuranceRunStatus.RUNNING, "to": AssuranceRunStatus.COMPLETED}
        },
        metadata={
            "assets_evaluated": run.assets_evaluated,
            "findings_generated": run.findings_generated,
            "findings_open": run.findings_open,
        },
        ip_address=ip_address,
    )
    return run


def _mark_run_running(*, run, organization, actor, ip_address=None):
    if run.status == AssuranceRunStatus.PENDING:
        run.status = AssuranceRunStatus.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=("status", "started_at", "updated_at"))
        audit(
            organization=organization,
            actor=actor,
            action="ASSURANCE_RUN_STARTED",
            entity_type="ASSURANCE_RUN",
            entity_id=run.pk,
            changes={
                "status": {
                    "from": AssuranceRunStatus.PENDING,
                    "to": AssuranceRunStatus.RUNNING,
                }
            },
            ip_address=ip_address,
        )
    elif run.status != AssuranceRunStatus.RUNNING:
        raise ValidationError({"status": "This assurance run cannot be executed."})


def dispatch_run(*, run_id, actor, ip_address=None):
    """Mark a durable run as running and publish its task only after commit."""
    organization = _organization(actor)
    with transaction.atomic():
        run = _locked_run(run_id, organization)
        if run.status == AssuranceRunStatus.COMPLETED:
            return run
        if run.status in (AssuranceRunStatus.FAILED, AssuranceRunStatus.CANCELLED):
            raise ValidationError(
                {"status": "This assurance run is terminal; create a new run to retry it."}
            )

        _mark_run_running(run=run, organization=organization, actor=actor, ip_address=ip_address)

        from assurance.tasks import execute_assurance_run

        transaction.on_commit(partial(execute_assurance_run.delay, str(run.pk)))
    return run


def execute_run(*, run_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        run = _locked_run(run_id, organization)
        if run.status == AssuranceRunStatus.COMPLETED:
            # A broker may redeliver after commit but before acknowledging the task.
            return run
        if run.status in (AssuranceRunStatus.FAILED, AssuranceRunStatus.CANCELLED):
            raise ValidationError(
                {"status": "This assurance run is terminal; create a new run to retry it."}
            )
        _mark_run_running(run=run, organization=organization, actor=actor, ip_address=ip_address)

    try:
        # RUNNING is retryable only after acquiring this row lock. A concurrent evaluator
        # holds it for the complete atomic evaluation; a crashed evaluator releases it and
        # rolls back all candidate writes, allowing safe re-entry with the same run ID.
        with transaction.atomic():
            return _evaluate_locked_run(run_id, organization, actor, ip_address)
    except Exception as exc:
        with transaction.atomic():
            failed_run = _locked_run(run_id, organization)
            if failed_run.status == AssuranceRunStatus.RUNNING:
                failed_run.status = AssuranceRunStatus.FAILED
                failed_run.completed_at = timezone.now()
                failed_run.completed_by = actor
                failed_run.failure_message = f"Evaluation failed ({type(exc).__name__})."
                failed_run.full_clean()
                failed_run.save(
                    update_fields=(
                        "status",
                        "completed_at",
                        "completed_by",
                        "failure_message",
                        "updated_at",
                    )
                )
                audit(
                    organization=organization,
                    actor=actor,
                    action="ASSURANCE_RUN_FAILED",
                    entity_type="ASSURANCE_RUN",
                    entity_id=failed_run.pk,
                    changes={
                        "status": {
                            "from": AssuranceRunStatus.RUNNING,
                            "to": AssuranceRunStatus.FAILED,
                        }
                    },
                    metadata={"failure_type": type(exc).__name__},
                    ip_address=ip_address,
                )
        return failed_run


def cancel_run(*, run_id, actor, ip_address=None):
    organization = _organization(actor)
    with transaction.atomic():
        run = _locked_run(run_id, organization)
        if run.status != AssuranceRunStatus.PENDING:
            raise ValidationError({"status": "Only pending assurance runs may be cancelled."})
        run.status = AssuranceRunStatus.CANCELLED
        run.completed_at = timezone.now()
        run.completed_by = actor
        run.full_clean()
        run.save(update_fields=("status", "completed_at", "completed_by", "updated_at"))
        audit(
            organization=organization,
            actor=actor,
            action="ASSURANCE_RUN_CANCELLED",
            entity_type="ASSURANCE_RUN",
            entity_id=run.pk,
            changes={"status": {"from": AssuranceRunStatus.PENDING, "to": run.status}},
            ip_address=ip_address,
        )
    return run
