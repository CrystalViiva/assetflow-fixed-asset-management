"""Kill real workers at transaction boundaries using only the isolated test database."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import pytest
from django.db import connection

from assurance.models import AssuranceFinding
from assurance.services import create_run, execute_run
from assurance.services.execution import advance_run

pytestmark = pytest.mark.django_db(transaction=True)

WORKER = """
import os, time, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from accounts.models import User
from assurance.services import execution, inputs
module = inputs if os.environ['KILL_PHASE'] == 'capture' else execution
names = {'capture':'capture', 'evaluate':'_evaluate_unit', 'publish':'_publish'}
name = names[os.environ['KILL_PHASE']]
original = getattr(module, name)
def interrupted(*args, **kwargs):
    original(*args, **kwargs)
    print('TRANSACTION_READY', flush=True)
    time.sleep(60)
setattr(module, name, interrupted)
actor = User.objects.get(pk=os.environ['KILL_ACTOR'])
execution.advance_run(run_id=os.environ['KILL_RUN'], actor=actor)
"""


@pytest.mark.parametrize("phase", ("capture", "evaluate", "publish"))
def test_real_worker_interruption(phase, manager, asset_factory, settings):
    settings.ASSURANCE_WORK_UNIT_SIZE = 1
    for _ in range(2):
        asset_factory(current_book_value="900.00")
    run = create_run(actor=manager, run_type="FULL")
    if phase != "capture":
        run = advance_run(run_id=run.pk, actor=manager)
        run = advance_run(run_id=run.pk, actor=manager)
    if phase == "publish":
        run = advance_run(run_id=run.pk, actor=manager)
    completed_before = run.units_completed
    candidates_before = run.candidates.count()
    db = connection.settings_dict
    # Never permit the child to accidentally connect to the application database.
    assert db["NAME"].startswith("test_")
    env = os.environ.copy()
    env["DATABASE_URL"] = (
        f"postgresql://{quote(db['USER'], safe='')}:{quote(db['PASSWORD'], safe='')}@"
        f"{db['HOST'] or 'localhost'}:{db['PORT'] or 5432}/{quote(db['NAME'], safe='')}"
    )
    env.update(
        KILL_PHASE=phase,
        KILL_RUN=str(run.pk),
        KILL_ACTOR=str(manager.pk),
        ASSURANCE_WORK_UNIT_SIZE="1",
    )
    proc = subprocess.Popen(
        [sys.executable, "-B", "-c", WORKER],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        with ThreadPoolExecutor(1) as pool:
            ready = pool.submit(proc.stdout.readline)
            try:
                line = ready.result(timeout=30).strip()
                if line != "TRANSACTION_READY":
                    try:
                        stdout, stderr = proc.communicate(timeout=1)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        stdout, stderr = proc.communicate(timeout=15)
                    pytest.fail(
                        "Worker exited before reaching the interruption point "
                        f"(stdout={stdout[-1000:]!r}, stderr={stderr[-4000:]!r})"
                    )
            finally:
                proc.kill()
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.communicate(timeout=15)
    run.refresh_from_db()
    assert run.units_completed == completed_before
    assert run.candidates.count() == candidates_before
    assert not AssuranceFinding.objects.exists()
    run = execute_run(run_id=run.pk, actor=manager)
    assert run.status == "COMPLETED"
    assert run.finding_occurrences.count() == 4


def test_failed_later_unit_retains_internal_progress(manager, asset_factory, settings, monkeypatch):
    from assurance.services import inputs

    settings.ASSURANCE_WORK_UNIT_SIZE = 1
    for _ in range(2):
        asset_factory()
    run = advance_run(run_id=create_run(actor=manager, run_type="FULL").pk, actor=manager)
    run = advance_run(run_id=run.pk, actor=manager)
    monkeypatch.setattr(inputs, "evaluate_input", lambda *args: (_ for _ in ()).throw(ValueError()))
    run = advance_run(run_id=run.pk, actor=manager)
    assert run.status == "FAILED" and run.units_completed == 1
    assert run.candidates.count() == 1
    assert not run.finding_occurrences.exists()


def test_lost_continuation_is_recovered(manager, asset_factory):
    from unittest.mock import patch

    from assurance.services.execution import recover_unfinished_runs
    from assurance.tasks import execute_assurance_run

    asset_factory()
    run = create_run(actor=manager, run_type="FULL")
    with patch.object(
        execute_assurance_run, "apply_async", side_effect=RuntimeError("broker down")
    ):
        assert execute_assurance_run.run(str(run.pk))["status"] == "RUNNING"
    run.refresh_from_db()
    assert run.sealed_at
    with patch.object(execute_assurance_run, "delay") as enqueue:
        assert recover_unfinished_runs() == 1
        enqueue.assert_called_once_with(str(run.pk))
    assert execute_run(run_id=run.pk, actor=manager).status == "COMPLETED"
