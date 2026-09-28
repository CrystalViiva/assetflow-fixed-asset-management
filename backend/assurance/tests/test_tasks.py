from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from assurance.models import AssuranceFinding, AssuranceRunStatus
from assurance.services import cancel_run, create_run, dispatch_run, execute_run
from assurance.tasks import execute_assurance_run
from audit.models import AuditLog


@pytest.mark.django_db(transaction=True)
def test_pending_run_dispatches_once_after_commit(manager):
    run = create_run(actor=manager, run_type="FULL")
    with patch("assurance.tasks.execute_assurance_run.delay") as enqueue:
        enqueue.side_effect = lambda *_args: assert_outside_transaction()
        with transaction.atomic():
            dispatched = dispatch_run(run_id=run.pk, actor=manager)
            enqueue.assert_not_called()

    enqueue.assert_called_once_with(str(run.pk))
    assert dispatched.status == AssuranceRunStatus.RUNNING
    assert (
        AuditLog.objects.filter(
            entity_id=str(run.pk), action="ASSURANCE_RUN_STARTED", user=manager
        ).count()
        == 1
    )


def assert_outside_transaction():
    assert not connection.in_atomic_block


@pytest.mark.django_db(transaction=True)
def test_dispatch_is_not_enqueued_if_surrounding_transaction_rolls_back(manager):
    run = create_run(actor=manager, run_type="FULL")
    with patch("assurance.tasks.execute_assurance_run.delay") as enqueue:
        with pytest.raises(RuntimeError, match="rollback dispatch"):
            with transaction.atomic():
                dispatch_run(run_id=run.pk, actor=manager)
                raise RuntimeError("rollback dispatch")

    run.refresh_from_db()
    assert run.status == AssuranceRunStatus.PENDING
    assert not AuditLog.objects.filter(
        entity_id=str(run.pk), action="ASSURANCE_RUN_STARTED"
    ).exists()
    enqueue.assert_not_called()


@pytest.mark.django_db
def test_assurance_task_completes_run_and_returns_json_safe_counts(manager, asset_factory):
    asset_factory(current_book_value=Decimal("900.00"))
    run = create_run(actor=manager, run_type="FULL")

    result = execute_assurance_run.run(str(run.pk))

    assert result == {
        "run_id": str(run.pk),
        "status": AssuranceRunStatus.COMPLETED,
        "assets_evaluated": 1,
        "findings_generated": 2,
    }
    assert all(type(value) in (str, int) for value in result.values())


@pytest.mark.django_db
def test_assurance_task_is_idempotent_for_completed_run(manager, asset_factory):
    asset_factory(current_book_value=Decimal("900.00"))
    run = create_run(actor=manager, run_type="FULL")

    first = execute_assurance_run.run(str(run.pk))
    occurrence_counts = list(
        AssuranceFinding.objects.filter(last_detected_run=run)
        .order_by("pk")
        .values_list("occurrence_count", flat=True)
    )
    repeated = execute_assurance_run.run(str(run.pk))

    assert repeated == first
    assert (
        list(
            AssuranceFinding.objects.filter(last_detected_run=run)
            .order_by("pk")
            .values_list("occurrence_count", flat=True)
        )
        == occurrence_counts
    )


@pytest.mark.django_db
@pytest.mark.parametrize("terminal_status", ("FAILED", "CANCELLED"))
def test_assurance_task_does_not_retry_terminal_runs(terminal_status, monkeypatch, manager):
    run = create_run(actor=manager, run_type="FULL")
    if terminal_status == "FAILED":
        monkeypatch.setattr(
            "assurance.services.runs._collect_candidates",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controlled failure")),
        )
        run = execute_run(run_id=run.pk, actor=manager)
    else:
        run = cancel_run(run_id=run.pk, actor=manager)

    with pytest.raises(ValidationError, match="terminal"):
        execute_assurance_run.run(str(run.pk))

    run.refresh_from_db()
    assert run.status == terminal_status


@pytest.mark.django_db(transaction=True)
def test_task_uses_run_started_by_for_completion_and_failure_audit(
    manager, admin_user, monkeypatch
):
    run = create_run(actor=manager, run_type="FULL")
    with patch("assurance.tasks.execute_assurance_run.delay"):
        dispatch_run(run_id=run.pk, actor=admin_user)

    def fail_candidates(*_args, **_kwargs):
        raise RuntimeError("controlled task failure")

    monkeypatch.setattr("assurance.services.runs._collect_candidates", fail_candidates)
    result = execute_assurance_run.run(str(run.pk))

    run.refresh_from_db()
    assert result["status"] == AssuranceRunStatus.FAILED
    assert run.completed_by_id == manager.pk
    assert (
        AuditLog.objects.get(entity_id=str(run.pk), action="ASSURANCE_RUN_STARTED").user_id
        == admin_user.pk
    )
    assert (
        AuditLog.objects.get(entity_id=str(run.pk), action="ASSURANCE_RUN_FAILED").user_id
        == manager.pk
    )


@pytest.mark.django_db(transaction=True)
def test_dispatch_and_task_keep_runs_organization_scoped(manager, foreign_manager, asset_factory):
    asset_factory(current_book_value=Decimal("900.00"))
    run = create_run(actor=manager, run_type="FULL")

    with patch("assurance.tasks.execute_assurance_run.delay") as enqueue:
        with pytest.raises(ValidationError, match="not found in your organization"):
            dispatch_run(run_id=run.pk, actor=foreign_manager)
        enqueue.assert_not_called()

    result = execute_assurance_run.run(str(run.pk))

    assert result["status"] == AssuranceRunStatus.COMPLETED
    assert not AssuranceFinding.objects.filter(organization=foreign_manager.organization).exists()
