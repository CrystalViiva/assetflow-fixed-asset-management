import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)


def test_legacy_records_remain_explicit(manager):
    old = ("assurance", "0002_remove_assurancerun_assurance_run_timestamps_valid_and_more")
    target = ("assurance", "0003_scalable_execution")
    executor = MigrationExecutor(connection)
    executor.migrate([old])
    try:
        apps = executor.loader.project_state([old]).apps
        Run = apps.get_model("assurance", "AssuranceRun")
        before = {}
        for status in ("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"):
            started = timezone.now() if status not in ("PENDING", "CANCELLED") else None
            ended = timezone.now() if status in ("COMPLETED", "FAILED", "CANCELLED") else None
            run = Run.objects.create(
                organization_id=manager.organization_id,
                started_by_id=manager.pk,
                run_type="FULL",
                status=status,
                started_at=started,
                completed_at=ended,
                completed_by_id=manager.pk if ended else None,
            )
            before[run.pk] = (status, started, ended)
    finally:
        MigrationExecutor(connection).migrate([target])
    from django.core.exceptions import ValidationError

    from assurance.models import AssuranceRun
    from assurance.services.execution import advance_run

    for run in AssuranceRun.objects.all():
        assert (run.status, run.started_at, run.completed_at) == before[run.pk]
        assert run.executor_version == 0 and run.execution_phase == "LEGACY"
        assert not run.inputs.exists()
        if run.status == "RUNNING":
            with pytest.raises(ValidationError, match="operator review"):
                advance_run(run_id=run.pk, actor=manager)
        if run.status == "PENDING":
            updated = advance_run(run_id=run.pk, actor=manager)
            assert updated.executor_version == 1 and updated.execution_phase == "PUBLISH"
