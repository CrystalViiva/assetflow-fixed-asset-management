"""Transactional assurance-run orchestration and finding deduplication."""

from functools import partial
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from assets.models import Asset
from assurance.constants import DAILY_FULL_SCHEDULE_ID
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
from assurance.services.inputs import EXECUTOR_VERSION
from organizations.models import Organization
from verification.models import CampaignStatus, VerificationCampaign
from verification.selectors import expected_assets

SEVERITY_RANK = {
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}


def _organization(actor, organization=None):
    organization_id = getattr(organization, "pk", organization)
    if actor is None:
        if organization_id is None:
            raise ValidationError({"organization": "An organization is required for system runs."})
        try:
            return Organization.objects.get(pk=organization_id)
        except Organization.DoesNotExist as exc:
            raise ValidationError({"organization": "Organization was not found."}) from exc
    if not getattr(actor, "organization_id", None):
        raise ValidationError({"organization": "The user must belong to an organization."})
    if organization_id is not None and actor.organization_id != organization_id:
        raise ValidationError({"organization": "The user is outside the requested organization."})
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
        executor_version=EXECUTOR_VERSION,
        scope=_scope(verification_campaign),
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
            run.scope = _scope(locked_campaign)
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


def create_scheduled_run(*, organization, scheduled_for):
    """Return the unique system-initiated FULL run for an organization and day."""
    organization_id = getattr(organization, "pk", organization)
    with transaction.atomic():
        try:
            organization = Organization.objects.select_for_update().get(
                pk=organization_id, is_active=True
            )
        except Organization.DoesNotExist as exc:
            raise ValidationError(
                {"organization": "Only active organizations may receive scheduled runs."}
            ) from exc

        existing = AssuranceRun.objects.filter(
            organization=organization, scheduled_for=scheduled_for
        ).first()
        if existing:
            return existing, False

        run = AssuranceRun(
            organization=organization,
            run_type=AssuranceRunType.FULL,
            scheduled_for=scheduled_for,
            started_by=None,
            executor_version=EXECUTOR_VERSION,
        )
        run.full_clean(validate_constraints=False)
        try:
            with transaction.atomic():
                run.save()
        except IntegrityError:
            existing = AssuranceRun.objects.get(
                organization=organization, scheduled_for=scheduled_for
            )
            return existing, False

        audit(
            organization=organization,
            actor=None,
            action="ASSURANCE_RUN_CREATED",
            entity_type="ASSURANCE_RUN",
            entity_id=run.pk,
            metadata={
                "run_type": run.run_type,
                "schedule_id": DAILY_FULL_SCHEDULE_ID,
                "scheduled_for": scheduled_for.isoformat(),
                "initiated_by": "system",
            },
        )
    return run, True


def _asset_population(run):
    """Capture population, using the run's frozen campaign predicates."""
    assets = Asset.objects.filter(organization_id=run.organization_id)
    if run.run_type == AssuranceRunType.PHYSICAL:
        assets = expected_assets(scope_campaign(run))
    return assets.select_related("department", "location").order_by("pk")


def _scope(campaign):
    if campaign is None:
        return {}
    return {
        "scope_type": campaign.scope_type,
        "department_id": str(campaign.department_id) if campaign.department_id else None,
        "location_id": str(campaign.location_id) if campaign.location_id else None,
    }


def scope_campaign(run):
    return SimpleNamespace(organization_id=run.organization_id, **run.scope)


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
        # The partial unique index arbitrates insertion races. Model validation still
        # checks fields and tenant relations, but must not preflight that constraint.
        finding.full_clean(validate_constraints=False)
        try:
            with transaction.atomic():
                finding.save()
        except IntegrityError as exc:
            if getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None) != (
                "assfinding_active_identity_uniq"
            ):
                raise
            # A concurrent run may have inserted the same active identity after our read.
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
                # The winner may have been closed by a reviewer before this reread.
                # Retry publication transactionally rather than losing this detection.
                from assurance.services.execution import RetryPublication

                raise RetryPublication from exc
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
    latest = (run.started_at, run.pk) >= (finding.last_detected_at, finding.last_detected_run_id)
    if latest:
        finding.last_detected_at = run.started_at
        finding.last_detected_run = run
    finding.severity = max((finding.severity, candidate.severity), key=SEVERITY_RANK.get)
    if latest:
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


def _mark_run_running(*, run, organization, actor, ip_address=None):
    if run.status == AssuranceRunStatus.PENDING:
        if run.executor_version == 0:
            run.executor_version = EXECUTOR_VERSION
            run.scope = _scope(run.verification_campaign)
            run.execution_phase = "CAPTURE"
        run.status = AssuranceRunStatus.RUNNING
        run.started_at = timezone.now()
        run.save(
            update_fields=(
                "status",
                "started_at",
                "updated_at",
                "executor_version",
                "scope",
                "execution_phase",
            )
        )
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


def dispatch_run(*, run_id, actor=None, organization=None, ip_address=None):
    """Mark a durable run as running and publish its task only after commit."""
    organization = _organization(actor, organization)
    if actor is None and not organization.is_active:
        raise ValidationError({"organization": "Inactive organizations cannot be scheduled."})
    with transaction.atomic():
        run = _locked_run(run_id, organization)
        if run.status == AssuranceRunStatus.COMPLETED:
            return run
        if run.status in (AssuranceRunStatus.FAILED, AssuranceRunStatus.CANCELLED):
            raise ValidationError(
                {"status": "This assurance run is terminal; create a new run to retry it."}
            )

        if run.status == "RUNNING" and run.executor_version != EXECUTOR_VERSION:
            raise ValidationError(
                "Legacy or incompatible RUNNING execution requires operator review."
            )

        _mark_run_running(run=run, organization=organization, actor=actor, ip_address=ip_address)

        from assurance.tasks import execute_assurance_run

        transaction.on_commit(partial(execute_assurance_run.delay, str(run.pk)))
    return run


def execute_run(*, run_id, actor, organization=None, ip_address=None):
    """Synchronous domain driver; each advancement owns a separate transaction."""
    from assurance.services.execution import advance_run

    while True:
        run = advance_run(
            run_id=run_id, actor=actor, organization=organization, ip_address=ip_address
        )
        if run.status != AssuranceRunStatus.RUNNING or run.next_attempt_at:
            return run


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
