import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from analytics.contracts import SNAPSHOT_REPORT_TYPES


def test_dag_parses_without_importing_django_or_running_extraction(monkeypatch):
    parsed = {}

    class TaskDefinition:
        def __init__(self, function=None, **options):
            self.function = function
            self.options = options

        def expand(self, **values):
            parsed.setdefault("mappings", []).append(values)
            return TaskRef("mapped")

        def __call__(self, *args, **kwargs):
            return TaskRef("task")

    class TaskRef:
        def __init__(self, name):
            self.name = name
            self.output = self

        def map(self, function):
            parsed["mapped_function"] = function
            return self

        def __rshift__(self, other):
            parsed.setdefault("dependencies", []).append((self.name, other.name))
            return other

    class SparkOperator:
        @classmethod
        def partial(cls, **options):
            parsed["spark_options"] = options
            return cls()

        def expand(self, **values):
            parsed["spark_mapping"] = values
            return TaskRef("spark")

    airflow = ModuleType("airflow")
    sdk = ModuleType("airflow.sdk")

    def dag(**options):
        def decorate(function):
            def parse_dag():
                parsed["dag"] = options
                function()

            return parse_dag

        return decorate

    def task(function=None, **options):
        if function is None:
            return lambda wrapped: TaskDefinition(wrapped, **options)
        return TaskDefinition(function, **options)

    sdk.dag = dag
    sdk.task = task
    sdk.get_current_context = lambda: (_ for _ in ()).throw(
        AssertionError("task execution must not happen during DAG parsing")
    )
    airflow.sdk = sdk
    provider = ModuleType("airflow.providers")
    apache = ModuleType("airflow.providers.apache")
    spark_provider = ModuleType("airflow.providers.apache.spark")
    operators = ModuleType("airflow.providers.apache.spark.operators")
    spark_submit = ModuleType("airflow.providers.apache.spark.operators.spark_submit")
    spark_submit.SparkSubmitOperator = SparkOperator
    monkeypatch.setitem(sys.modules, "airflow.providers", provider)
    monkeypatch.setitem(sys.modules, "airflow.providers.apache", apache)
    monkeypatch.setitem(sys.modules, "airflow.providers.apache.spark", spark_provider)
    monkeypatch.setitem(sys.modules, "airflow.providers.apache.spark.operators", operators)
    monkeypatch.setitem(
        sys.modules, "airflow.providers.apache.spark.operators.spark_submit", spark_submit
    )
    monkeypatch.setitem(sys.modules, "airflow", airflow)
    monkeypatch.setitem(sys.modules, "airflow.sdk", sdk)

    dag_path = Path(__file__).parents[3] / "airflow" / "dags" / "assetflow_report_snapshots.py"
    specification = importlib.util.spec_from_file_location("assetflow_analytics_dag_test", dag_path)
    module = importlib.util.module_from_spec(specification)
    monkeypatch.setitem(sys.modules, specification.name, module)
    specification.loader.exec_module(module)

    assert parsed["dag"]["dag_id"] == "assetflow_report_snapshot_analytics_v1"
    assert parsed["dag"]["default_args"]["retries"] == 2
    assert parsed["dag"]["max_active_runs"] == 1
    assert parsed["mappings"][0]["report_type"] == list(SNAPSHOT_REPORT_TYPES)
    assert parsed["spark_options"]["conn_id"] == "spark_default"
    assert parsed["spark_options"]["deploy_mode"] == "client"
    assert parsed["spark_options"]["retries"] == 2
    assert parsed["spark_options"]["total_executor_cores"] == 2
    assert parsed["spark_mapping"]["application_args"] is not None
    assert len(parsed["dependencies"]) == 2


def test_dag_has_no_transactional_model_mutations_or_sql():
    dag_path = Path(__file__).parents[3] / "airflow" / "dags" / "assetflow_report_snapshots.py"
    source = dag_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "django.db" not in source
    assert "execute(" not in source.lower()
    assert not any(
        isinstance(node, ast.Attribute) and node.attr in {"save", "update", "delete"}
        for node in ast.walk(tree)
    )
    assert "extract_analytics_snapshots" in source
    assert "prepare_curated_spark_runs" in source
    assert "publish_curated_spark_run" in source
    assert "SparkSubmitOperator" in source
