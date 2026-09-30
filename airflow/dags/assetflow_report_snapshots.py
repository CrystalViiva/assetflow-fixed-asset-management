"""Orchestrate Django-owned snapshot extraction; DAG parsing performs no I/O."""

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from airflow.sdk import dag, get_current_context, task
from analytics.contracts import SNAPSHOT_REPORT_TYPES

BACKEND_DIR = Path("/opt/assetflow/backend")


@dag(
    dag_id="assetflow_report_snapshot_analytics_v1",
    description="Extract immutable, organization-scoped report snapshots to JSONL.",
    schedule="0 3 * * *",
    start_date=datetime(2026, 1, 1, tzinfo=ZoneInfo("Africa/Lagos")),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["assetflow", "analytics", "contract-v1"],
)
def assetflow_report_snapshot_analytics():
    @task
    def extract_report_type(report_type):
        context = get_current_context()
        run_key = context["dag_run"].run_id
        environment = os.environ.copy()
        existing_pythonpath = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = (
            f"{BACKEND_DIR}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(BACKEND_DIR)
        )
        command = [
            sys.executable,
            "manage.py",
            "extract_analytics_snapshots",
            "--report-type",
            report_type,
            "--run-key",
            run_key,
        ]
        result = subprocess.run(
            command,
            cwd=BACKEND_DIR,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(
                f"Django analytics extraction failed for {report_type} "
                f"(exit {result.returncode}); child output is suppressed to avoid leaking configuration."
            )
        return result.stdout

    extract_report_type.expand(report_type=list(SNAPSHOT_REPORT_TYPES))


assetflow_report_snapshot_analytics()
