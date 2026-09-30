import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from analytics.contracts import SNAPSHOT_REPORT_TYPES


def test_dag_parses_without_importing_django_or_running_extraction(monkeypatch):
    parsed = {}

    class TaskDefinition:
        def __init__(self, function):
            self.function = function

        def expand(self, **values):
            parsed["mapping"] = values

    airflow = ModuleType("airflow")
    sdk = ModuleType("airflow.sdk")

    def dag(**options):
        def decorate(function):
            def parse_dag():
                parsed["dag"] = options
                function()

            return parse_dag

        return decorate

    sdk.dag = dag
    sdk.task = lambda function: TaskDefinition(function)
    sdk.get_current_context = lambda: (_ for _ in ()).throw(
        AssertionError("task execution must not happen during DAG parsing")
    )
    airflow.sdk = sdk
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
    assert parsed["mapping"]["report_type"] == list(SNAPSHOT_REPORT_TYPES)


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
