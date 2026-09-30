"""Small reproducible PostgreSQL baselines; these are not capacity claims."""

import json
import subprocess
import sys
import time
import tracemalloc
from types import ModuleType
from uuid import uuid4

import pytest
from django.db import connection

from assets.models import Asset
from assurance.services import create_run, execute_run
from assurance.services.execution import advance_run
from verification.models import PhysicalVerification

pytestmark = pytest.mark.django_db(transaction=True)
BASELINE = "f9a915c9198751ec4ddf0ea4440a9ec3a2c13918"


def historical_module(path, name):
    result = subprocess.run(
        ["git", "show", f"{BASELINE}:backend/{path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        # Shallow CI checkouts still exercise the new engine at every population.
        return None
    module = ModuleType(name)
    sys.modules[name] = module
    exec(compile(result.stdout, path, "exec"), module.__dict__)
    return module


def measure(call):
    queries = 0
    asset_locks = 0

    def count(execute, sql, params, many, context):
        nonlocal queries, asset_locks
        queries += 1
        asset_locks += int('FOR UPDATE OF "assets_asset"' in sql)
        return execute(sql, params, many, context)

    tracemalloc.start()
    start = time.perf_counter()
    with connection.execute_wrapper(count):
        result = call()
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, {
        "queries": queries,
        "seconds": round(elapsed, 3),
        "python_peak_mib": round(peak / 1048576, 3),
        "asset_lock_queries": asset_locks,
    }


@pytest.mark.parametrize("population", (100, 500, 1000))
def test_postgresql_scaling(population, manager, asset_factory, campaign_factory, settings):
    settings.ASSURANCE_WORK_UNIT_SIZE = 100
    template = asset_factory()
    assets = [template]
    for index in range(1, population):
        values = {
            field.attname: getattr(template, field.attname)
            for field in Asset._meta.concrete_fields
            if not field.primary_key
        }
        values["asset_tag"] = f"BENCH-{index}"
        assets.append(Asset(id=uuid4(), **values))
    Asset.objects.bulk_create(assets[1:], batch_size=100)
    campaign = campaign_factory()
    PhysicalVerification.objects.bulk_create(
        [
            PhysicalVerification(
                organization=manager.organization,
                campaign=campaign,
                asset=asset,
                verified_by=manager,
                result="VERIFIED",
                observed_asset_tag=asset.asset_tag,
                observed_department_id=asset.department_id,
                observed_location_id=asset.location_id,
                observed_condition=asset.condition,
            )
            for asset in assets
        ],
        batch_size=100,
    )
    old = historical_module("assurance/services/runs.py", "assurance_baseline_runs")
    old_context = historical_module("assurance/rules/context.py", "assurance_baseline_context")
    before = {"unavailable": "Historical Git object absent in this checkout"}
    if old and old_context:
        old.build_context = old_context.build_context
        legacy = create_run(actor=manager, run_type="OPERATIONAL")
        old_result, before = measure(lambda: old.execute_run(run_id=legacy.pk, actor=manager))
        assert old_result.status == "COMPLETED" and old_result.findings_generated == 0
    run = create_run(actor=manager, run_type="OPERATIONAL")
    run, capture = measure(lambda run=run: advance_run(run_id=run.pk, actor=manager))
    unit_measurements = []
    while run.execution_phase == "EVALUATE":
        run, unit = measure(lambda run=run: advance_run(run_id=run.pk, actor=manager))
        unit_measurements.append(unit)
    run, publication = measure(lambda run=run: advance_run(run_id=run.pk, actor=manager))
    assert run.status == "COMPLETED" and run.assets_evaluated == population
    assert run.findings_generated == 0
    assert capture["asset_lock_queries"] == publication["asset_lock_queries"] == 0
    assert max(m["queries"] for m in unit_measurements) <= 25
    print(
        "\nASSURANCE_BENCHMARK "
        + json.dumps(
            {
                "population": population,
                "batch_size": 100,
                "baseline": before,
                "capture": capture,
                "evaluation_queries": sum(m["queries"] for m in unit_measurements),
                "evaluation_seconds": round(sum(m["seconds"] for m in unit_measurements), 3),
                "largest_unit_peak_mib": max(m["python_peak_mib"] for m in unit_measurements),
                "publication": publication,
            }
        )
    )


def test_dense_findings_publication(manager, asset_factory, settings):
    settings.ASSURANCE_WORK_UNIT_SIZE = 10
    for _ in range(25):
        asset_factory(current_book_value="900.00")
    run = advance_run(run_id=create_run(actor=manager, run_type="FINANCIAL").pk, actor=manager)
    while run.execution_phase == "EVALUATE":
        run = advance_run(run_id=run.pk, actor=manager)
    run, measurement = measure(lambda: execute_run(run_id=run.pk, actor=manager))
    assert run.status == "COMPLETED" and run.findings_generated == 50
    print("\nASSURANCE_PUBLICATION " + json.dumps(measurement))
