"""Orchestrate Django-owned snapshot extraction; DAG parsing performs no I/O."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.sdk import dag, get_current_context, task
from analytics.contracts import SNAPSHOT_REPORT_TYPES

BACKEND_DIR = Path("/opt/assetflow/backend")
SPARK_JOB = "/opt/assetflow/spark/assetflow_spark/job.py"


def _spark_application_args(batch):
    return batch["spark_args"]


@dag(
    dag_id="assetflow_report_snapshot_analytics_v1",
    description="Extract contract-v1 snapshots and publish tenant-scoped Spark marts.",
    schedule="0 3 * * *",
    start_date=datetime(2026, 1, 1, tzinfo=ZoneInfo("Africa/Lagos")),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=8,
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

    @task(retries=2, retry_delay=timedelta(minutes=5))
    def prepare_curated_runs():
        environment = os.environ.copy()
        environment["PYTHONPATH"] = (
            f"{BACKEND_DIR}{os.pathsep}{environment.get('PYTHONPATH', '')}"
        ).rstrip(os.pathsep)
        result = subprocess.run(
            [sys.executable, "manage.py", "prepare_curated_spark_runs"],
            cwd=BACKEND_DIR,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(
                "Could not prepare fenced Spark inputs; child output is suppressed to avoid leaking configuration."
            )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Spark input preparation returned invalid metadata."
            ) from exc

    @task(retries=2, retry_delay=timedelta(minutes=5))
    def publish_curated_run(batch):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = (
            f"{BACKEND_DIR}{os.pathsep}{environment.get('PYTHONPATH', '')}"
        ).rstrip(os.pathsep)
        result = subprocess.run(
            [
                sys.executable,
                "manage.py",
                "publish_curated_spark_run",
                "--run-id",
                batch["run_id"],
                "--attempt-token",
                batch["attempt_token"],
            ],
            cwd=BACKEND_DIR,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(
                "Curated publication verification failed; child output is suppressed to avoid leaking configuration."
            )
        return result.stdout

    extracted = extract_report_type.expand(report_type=list(SNAPSHOT_REPORT_TYPES))
    prepared = prepare_curated_runs()
    spark = SparkSubmitOperator.partial(
        task_id="transform_curated_tenant",
        application=SPARK_JOB,
        conn_id="spark_default",
        deploy_mode="client",
        total_executor_cores=2,
        executor_memory="1G",
        driver_memory="1G",
        conf={
            "spark.driver.host": "airflow-dev",
            "spark.driver.bindAddress": "0.0.0.0",
            "spark.sql.session.timeZone": "UTC",
            "spark.sql.ansi.enabled": "true",
            "spark.sql.shuffle.partitions": "8",
        },
        retries=2,
        retry_delay=timedelta(minutes=5),
        verbose=False,
        do_xcom_push=False,
    ).expand(application_args=prepared.output.map(_spark_application_args))
    published = publish_curated_run.expand(batch=prepared)
    extracted >> prepared
    spark >> published


assetflow_report_snapshot_analytics()
