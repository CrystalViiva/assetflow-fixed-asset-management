"""Durable per-run advancement. PostgreSQL owns claims, progress and publication."""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import InterfaceError, OperationalError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from assurance.models import AssuranceRun, AssuranceRunCandidate, AssuranceRunStatus
from assurance.services import inputs
from assurance.services.audit import audit


class RetryPublication(Exception):
    """An active identity changed while resolving a concurrent insertion."""


def _transient(exc):
    code = getattr(exc.__cause__, "sqlstate", None)
    return isinstance(exc, (RetryPublication, InterfaceError)) or (
        isinstance(exc, OperationalError)
        and (code is None or code in {"40001", "40P01", "55P03", "57014"} or code.startswith("08"))
    )


def _evaluate_unit(run):
    unit = run.work_units.filter(completed_at__isnull=True).order_by("ordinal").first()
    if unit is None:
        run.execution_phase = "PUBLISH"
        return
    rows = list(
        run.inputs.filter(subject_ordinal__range=(unit.first_subject, unit.last_subject)).order_by(
            "subject_ordinal"
        )
    )
    if len(rows) != unit.last_subject - unit.first_subject + 1:
        raise ValueError("Incomplete assurance work-unit population.")
    pending = []
    observations = inputs.observations_for_unit(run, rows) if run.run_type != "FINANCIAL" else {}
    for row in rows:
        for candidate in inputs.evaluate_input(run, row, observations):
            pending.append(
                AssuranceRunCandidate(
                    run=run,
                    subject_ordinal=row.subject_ordinal,
                    identity_key=candidate.identity_key,
                    finding_type=candidate.finding_type,
                    payload=inputs.candidate_payload(candidate),
                )
            )
    AssuranceRunCandidate.objects.bulk_create(pending, batch_size=run.work_unit_size)
    unit.completed_at = timezone.now()
    unit.candidate_count = len(pending)
    unit.save(update_fields=("completed_at", "candidate_count"))
    run.units_completed += 1
    if run.units_completed == run.unit_count:
        run.execution_phase = "PUBLISH"


def _publish(run, actor, ip_address):
    from assurance.services.runs import _record_candidate

    end = 0
    count = 0
    candidates = 0
    for unit in run.work_units.order_by("ordinal").iterator(chunk_size=run.work_unit_size):
        if (
            not unit.completed_at
            or unit.ordinal != count
            or unit.first_subject != end + 1
            or unit.last_subject != min(end + run.work_unit_size, run.subject_count)
        ):
            raise ValueError("Assurance manifest is incomplete.")
        end = unit.last_subject
        count += 1
        candidates += unit.candidate_count
    if (
        not run.sealed_at
        or count != run.unit_count
        or count != run.units_completed
        or end != run.subject_count
        or run.inputs.filter(subject_ordinal__isnull=False).count() != run.subject_count
        or run.candidates.count() != candidates
    ):
        raise ValueError("Assurance completion gate failed.")
    for row in run.candidates.order_by("identity_key", "finding_type").iterator(
        chunk_size=run.work_unit_size
    ):
        _record_candidate(
            run=run,
            actor=actor,
            candidate=inputs.candidate_from_payload(row.payload),
            ip_address=ip_address,
        )
    run.status = AssuranceRunStatus.COMPLETED
    run.execution_phase = "DONE"
    run.completed_at = timezone.now()
    run.completed_by = actor
    run.assets_evaluated = run.population_count
    run.findings_generated = candidates
    # Publication locks every affected active finding until commit.
    run.findings_open = candidates
    run.findings_resolved = 0
    audit(
        organization=run.organization,
        actor=actor,
        action="ASSURANCE_RUN_COMPLETED",
        entity_type="ASSURANCE_RUN",
        entity_id=run.pk,
        changes={"status": {"from": "RUNNING", "to": "COMPLETED"}},
        metadata={
            "assets_evaluated": run.assets_evaluated,
            "findings_generated": candidates,
            "findings_open": candidates,
        },
        ip_address=ip_address,
    )


def advance_run(*, run_id, actor, organization=None, ip_address=None):
    """Advance one phase/unit. Never join an outer transaction during capture."""
    from assurance.services.runs import _locked_run, _mark_run_running, _organization

    if connection.in_atomic_block:
        raise ValidationError("Assurance execution requires its own top-level transactions.")
    organization = _organization(actor, organization)
    with transaction.atomic():
        run = _locked_run(run_id, organization)
        if run.status == AssuranceRunStatus.COMPLETED:
            return run
        if run.status in (AssuranceRunStatus.FAILED, AssuranceRunStatus.CANCELLED):
            raise ValidationError("This assurance run is terminal; create a new run to retry it.")
        if run.status == "RUNNING" and run.executor_version != inputs.EXECUTOR_VERSION:
            raise ValidationError(
                "Legacy or incompatible RUNNING execution requires operator review."
            )
        _mark_run_running(run=run, organization=organization, actor=actor, ip_address=ip_address)
        if run.next_attempt_at and run.next_attempt_at > timezone.now():
            return run
    revision = run.revision
    try:
        with transaction.atomic():
            if run.execution_phase == "CAPTURE":
                if connection.vendor != "postgresql":
                    raise ValidationError("Assurance capture requires PostgreSQL.")
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            run = _locked_run(run_id, organization)
            revision = run.revision
            if run.status != "RUNNING":
                return run
            if run.next_attempt_at and run.next_attempt_at > timezone.now():
                return run
            if run.executor_version != inputs.EXECUTOR_VERSION:
                raise ValueError("Incompatible assurance evaluator version.")
            if run.sealed_at and run.input_schema_version != inputs.INPUT_VERSION:
                raise ValueError("Incompatible sealed assurance input schema.")
            if run.execution_phase == "CAPTURE":
                size = settings.ASSURANCE_WORK_UNIT_SIZE
                if size < 1 or size > 10_000:
                    raise ValueError("ASSURANCE_WORK_UNIT_SIZE must be between 1 and 10000.")
                with connection.cursor() as cursor:
                    cursor.execute("SELECT transaction_timestamp()")
                    run.captured_at = cursor.fetchone()[0]
                inputs.capture(run, size)
                audit(
                    organization=organization,
                    actor=actor,
                    action="ASSURANCE_INPUTS_SEALED",
                    entity_type="ASSURANCE_RUN",
                    entity_id=run.pk,
                    metadata={
                        "input_schema_version": inputs.INPUT_VERSION,
                        "executor_version": inputs.EXECUTOR_VERSION,
                        "population_count": run.population_count,
                        "subject_count": run.subject_count,
                        "unit_count": run.unit_count,
                    },
                )
            elif run.execution_phase == "EVALUATE":
                _evaluate_unit(run)
            elif run.execution_phase == "PUBLISH":
                _publish(run, actor, ip_address)
            else:
                raise ValueError("Invalid assurance execution phase.")
            run.revision += 1
            run.retry_count = 0
            run.next_attempt_at = None
            run.save()
            return run
    except Exception as exc:
        with transaction.atomic():
            failed = _locked_run(run_id, organization)
            # Another worker may have succeeded after this transaction released its lock.
            if failed.status != "RUNNING" or failed.revision != revision:
                return failed
            if _transient(exc) and failed.retry_count < settings.ASSURANCE_MAX_TRANSIENT_RETRIES:
                failed.retry_count += 1
                failed.next_attempt_at = timezone.now() + timedelta(
                    seconds=settings.ASSURANCE_RETRY_SECONDS * 2 ** (failed.retry_count - 1)
                )
                failed.save(update_fields=("retry_count", "next_attempt_at", "updated_at"))
                audit(
                    organization=organization,
                    actor=actor,
                    action="ASSURANCE_EXECUTION_RETRY",
                    entity_type="ASSURANCE_RUN",
                    entity_id=failed.pk,
                    metadata={
                        "failure_type": type(exc).__name__,
                        "retry_count": failed.retry_count,
                        "phase": failed.execution_phase,
                    },
                )
                return failed
            failed.status = AssuranceRunStatus.FAILED
            failed.completed_at = timezone.now()
            failed.completed_by = actor
            failed.failure_message = f"Evaluation failed ({type(exc).__name__})."
            failed.next_attempt_at = None
            failed.save()
            audit(
                organization=organization,
                actor=actor,
                action="ASSURANCE_RUN_FAILED",
                entity_type="ASSURANCE_RUN",
                entity_id=failed.pk,
                changes={"status": {"from": "RUNNING", "to": "FAILED"}},
                metadata={"failure_type": type(exc).__name__},
                ip_address=ip_address,
            )
            return failed


def recover_unfinished_runs(*, limit=100):
    """Bounded redispatch, including committed progress whose next publish was lost."""
    from assurance.tasks import execute_assurance_run

    now = timezone.now()
    with transaction.atomic():
        runs = list(
            AssuranceRun.objects.select_for_update(skip_locked=True)
            .filter(
                status="RUNNING",
                executor_version=inputs.EXECUTOR_VERSION,
            )
            .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
            .order_by("updated_at", "pk")[:limit]
        )
        for run in runs:
            # Fair redispatch even when there are more eligible runs than one scan.
            run.save(update_fields=("updated_at",))
            transaction.on_commit(
                lambda pk=str(run.pk): execute_assurance_run.delay(pk), robust=True
            )
    return len(runs)
