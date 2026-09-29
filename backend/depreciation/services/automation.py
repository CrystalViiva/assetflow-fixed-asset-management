"""Durable orchestration for scheduled monthly depreciation posting."""

import logging
import uuid
from datetime import date
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Count, Sum
from django.utils import timezone

from audit.services import record_event
from depreciation.models import (
    AccountingPeriod,
    DepreciationEntry,
    DepreciationRun,
    DepreciationRunSource,
    DepreciationRunStatus,
    PeriodStatus,
)
from depreciation.selectors import active_organizations_for_depreciation, schedules_due_for_period
from depreciation.services.posting import next_period_for_schedule, post_depreciation

logger = logging.getLogger(__name__)


def _window_start(window):
    window = window or timezone.localdate()
    if isinstance(window, str):
        window = date.fromisoformat(window)
    return date(window.year, window.month, 1)


def _summary(run):
    return {
        "run_id": str(run.pk),
        "organization_id": str(run.organization_id),
        "scheduled_for": run.scheduled_for.isoformat(),
        "status": run.status,
        "schedules_considered": run.schedules_considered,
        "assets_considered": run.assets_considered,
        "entries_posted": run.entries_posted,
        "total_depreciation_posted": str(run.total_depreciation_posted),
        "failure_class": run.failure_class or None,
        "failure_message": run.failure_message or None,
    }


def _mark_failed(run, failure_class, message):
    previous_status = run.status
    run.status = DepreciationRunStatus.FAILED
    run.failed_at = timezone.now()
    run.failure_class = failure_class[:100]
    run.failure_message = str(message)[:500]
    run.save(
        update_fields=(
            "status",
            "failed_at",
            "failure_class",
            "failure_message",
            "updated_at",
        )
    )
    record_event(
        organization=run.organization,
        user=None,
        action="DEPRECIATION_RUN_FAILED",
        entity_type="DEPRECIATION_RUN",
        entity_id=run.pk,
        changes={"status": {"from": previous_status, "to": run.status}},
        metadata={
            "scheduled_for": run.scheduled_for.isoformat(),
            "failure_class": run.failure_class,
            "failure_message": run.failure_message,
        },
    )


def _period_outcome(run, status, failure_class, message):
    run.status = status
    run.failed_at = timezone.now()
    run.failure_class = failure_class
    run.failure_message = message
    run.save(
        update_fields=("status", "failed_at", "failure_class", "failure_message", "updated_at")
    )
    record_event(
        organization=run.organization,
        user=None,
        action="DEPRECIATION_RUN_FAILED",
        entity_type="DEPRECIATION_RUN",
        entity_id=run.pk,
        changes={"status": {"from": DepreciationRunStatus.PENDING, "to": status}},
        metadata={
            "scheduled_for": run.scheduled_for.isoformat(),
            "failure_class": failure_class,
            "failure_message": message,
        },
    )


def _enqueue_after_commit(run_id):
    from depreciation.tasks import execute_monthly_depreciation_run

    transaction.on_commit(lambda: execute_monthly_depreciation_run.delay(str(run_id)))


def schedule_organization_depreciation(organization, *, window):
    """Persist one month run and register execution only after its transaction commits."""
    scheduled_for = _window_start(window)
    with transaction.atomic():
        organization = (
            type(organization).objects.select_for_update().get(pk=organization.pk, is_active=True)
        )
        period = AccountingPeriod.objects.filter(
            organization=organization, year=scheduled_for.year, month=scheduled_for.month
        ).first()
        run, created = DepreciationRun.objects.get_or_create(
            organization=organization,
            scheduled_for=scheduled_for,
            source=DepreciationRunSource.SCHEDULED,
            defaults={"accounting_period": period},
        )
        if created:
            record_event(
                organization=organization,
                user=None,
                action="DEPRECIATION_RUN_SCHEDULED",
                entity_type="DEPRECIATION_RUN",
                entity_id=run.pk,
                changes={"status": {"from": None, "to": run.status}},
                metadata={
                    "scheduled_for": scheduled_for.isoformat(),
                    "accounting_period_id": str(period.pk) if period else None,
                },
            )
            if period is None:
                _period_outcome(
                    run,
                    DepreciationRunStatus.FAILED,
                    "AccountingPeriodMissing",
                    f"No accounting period exists for {scheduled_for:%Y-%m}.",
                )
            elif period.status != PeriodStatus.OPEN:
                _period_outcome(
                    run,
                    DepreciationRunStatus.FAILED,
                    "AccountingPeriodClosed",
                    f"Accounting period {scheduled_for:%Y-%m} is closed.",
                )

        should_dispatch = (
            run.status in (DepreciationRunStatus.PENDING, DepreciationRunStatus.RUNNING)
            and run.accounting_period_id is not None
        )
        if should_dispatch:
            _enqueue_after_commit(run.pk)
    return run, created


def schedule_monthly_depreciation(*, window=None):
    """Create/dispatch one durable monthly run for every currently active organization."""
    scheduled_for = _window_start(window)
    organization_ids = list(active_organizations_for_depreciation().values_list("pk", flat=True))
    result = {
        "schedule_id": "monthly-depreciation-posting",
        "window": scheduled_for.isoformat(),
        "organizations_considered": len(organization_ids),
        "runs_created": 0,
        "runs_skipped_existing": 0,
        "runs_not_dispatched": [],
        "organizations_failed": [],
        "run_ids": [],
    }
    for organization_id in organization_ids:
        try:
            organization = (
                active_organizations_for_depreciation().filter(pk=organization_id).first()
            )
            if organization is None:
                continue
            run, created = schedule_organization_depreciation(organization, window=scheduled_for)
            result["runs_created" if created else "runs_skipped_existing"] += 1
            result["run_ids"].append(str(run.pk))
            if run.status in (DepreciationRunStatus.FAILED, DepreciationRunStatus.COMPLETED):
                result["runs_not_dispatched"].append(
                    {
                        "run_id": str(run.pk),
                        "status": run.status,
                        "reason": run.failure_class or "already complete",
                    }
                )
        except Exception as exc:
            logger.exception(
                "Monthly depreciation scheduling failed for organization %s in window %s",
                organization_id,
                scheduled_for.isoformat(),
                extra={
                    "organization_id": str(organization_id),
                    "window": scheduled_for.isoformat(),
                },
            )
            result["organizations_failed"].append(
                {"organization_id": str(organization_id), "error_type": type(exc).__name__}
            )
    return result


def _try_run_lock(run_id):
    if connection.vendor != "postgresql":
        return True, None
    lock_id = uuid.UUID(str(run_id)).int & ((1 << 63) - 1)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
        acquired = cursor.fetchone()[0]
    return acquired, lock_id


def _release_run_lock(lock_id):
    if lock_id is not None and connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])


def _system_posting_totals(run):
    totals = DepreciationEntry.objects.filter(
        organization_id=run.organization_id,
        accounting_period_id=run.accounting_period_id,
        created_by__isnull=True,
    ).aggregate(count=Count("pk"), amount=Sum("depreciation_amount"))
    return totals["count"], totals["amount"] or Decimal("0.00")


def _persist_progress(run):
    count, total = _system_posting_totals(run)
    with transaction.atomic():
        locked = DepreciationRun.objects.select_for_update().get(pk=run.pk)
        locked.entries_posted = count
        locked.total_depreciation_posted = total
        locked.save(update_fields=("entries_posted", "total_depreciation_posted", "updated_at"))
    run.entries_posted = count
    run.total_depreciation_posted = total


def execute_monthly_run(*, run_id):
    """Execute a persisted run by delegating each ledger posting to post_depreciation."""
    acquired, lock_id = _try_run_lock(run_id)
    run = DepreciationRun.objects.select_related("organization", "accounting_period").get(pk=run_id)
    if not acquired:
        return _summary(run)
    try:
        with transaction.atomic():
            run = (
                DepreciationRun.objects.select_for_update(of=("self",))
                .select_related("organization", "accounting_period")
                .get(pk=run_id)
            )
            if run.status in (DepreciationRunStatus.COMPLETED, DepreciationRunStatus.FAILED):
                return _summary(run)
            if run.accounting_period is None or run.accounting_period.status != PeriodStatus.OPEN:
                _mark_failed(
                    run,
                    "AccountingPeriodUnavailable",
                    "The scheduled accounting period is missing or closed.",
                )
                return _summary(run)
            if run.status == DepreciationRunStatus.PENDING:
                run.status = DepreciationRunStatus.RUNNING
                run.started_at = timezone.now()
                run.save(update_fields=("status", "started_at", "updated_at"))
                record_event(
                    organization=run.organization,
                    user=None,
                    action="DEPRECIATION_RUN_STARTED",
                    entity_type="DEPRECIATION_RUN",
                    entity_id=run.pk,
                    changes={"status": {"from": DepreciationRunStatus.PENDING, "to": run.status}},
                    metadata={"scheduled_for": run.scheduled_for.isoformat()},
                )

        schedules = list(schedules_due_for_period(run.organization, run.accounting_period))
        run.schedules_considered = len(schedules)
        run.assets_considered = len(schedules)
        run.save(update_fields=("schedules_considered", "assets_considered", "updated_at"))

        due = []
        for schedule in schedules:
            existing = DepreciationEntry.objects.filter(
                organization_id=run.organization_id,
                schedule=schedule,
                accounting_period=run.accounting_period,
            ).exists()
            if existing:
                continue
            posted_count = DepreciationEntry.objects.filter(schedule=schedule).count()
            expected = next_period_for_schedule(schedule, posted_count)
            if expected < run.accounting_period.first_day:
                raise ValueError(
                    f"Schedule for asset {schedule.asset.asset_tag} is behind; "
                    f"next required period is {expected:%Y-%m}."
                )
            if expected > run.accounting_period.first_day:
                raise ValueError(
                    f"Schedule for asset {schedule.asset.asset_tag} has entries beyond "
                    "the target period or an inconsistent sequence."
                )
            if schedule.end_date < run.accounting_period.first_day:
                continue
            if posted_count >= schedule.useful_life_months:
                raise ValueError(
                    f"Schedule for asset {schedule.asset.asset_tag} is active but fully posted."
                )
            due.append(schedule)

        for schedule in due:
            post_depreciation(
                asset_id=schedule.asset_id,
                period_id=run.accounting_period_id,
                actor=None,
                organization=run.organization,
            )
            _persist_progress(run)

        with transaction.atomic():
            run = DepreciationRun.objects.select_for_update().get(pk=run.pk)
            run.entries_posted, run.total_depreciation_posted = _system_posting_totals(run)
            run.status = DepreciationRunStatus.COMPLETED
            run.completed_at = timezone.now()
            run.save(
                update_fields=(
                    "entries_posted",
                    "total_depreciation_posted",
                    "status",
                    "completed_at",
                    "updated_at",
                )
            )
            record_event(
                organization=run.organization,
                user=None,
                action="DEPRECIATION_RUN_COMPLETED",
                entity_type="DEPRECIATION_RUN",
                entity_id=run.pk,
                changes={"status": {"from": DepreciationRunStatus.RUNNING, "to": run.status}},
                metadata={
                    "scheduled_for": run.scheduled_for.isoformat(),
                    "entries_posted": run.entries_posted,
                    "total_depreciation_posted": str(run.total_depreciation_posted),
                },
            )
        return _summary(run)
    except Exception as exc:
        with transaction.atomic():
            run = (
                DepreciationRun.objects.select_for_update()
                .select_related("organization")
                .get(pk=run_id)
            )
            if run.status not in (DepreciationRunStatus.COMPLETED, DepreciationRunStatus.FAILED):
                if run.accounting_period_id:
                    run.entries_posted, run.total_depreciation_posted = _system_posting_totals(run)
                _mark_failed(run, type(exc).__name__, str(exc))
        logger.exception("Monthly depreciation run %s failed", run_id)
        return _summary(run)
    finally:
        _release_run_lock(lock_id)
