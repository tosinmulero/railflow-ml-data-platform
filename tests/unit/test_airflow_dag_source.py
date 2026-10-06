"""Static tests for the RailFlow Airflow DAG."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DAG_FILE = (
    PROJECT_ROOT
    / "airflow"
    / "dags"
    / "railflow_end_to_end.py"
)


def test_dag_file_exists() -> None:
    """DAG source must exist."""

    assert DAG_FILE.exists()


def test_dag_is_valid_python() -> None:
    """DAG must parse as valid Python."""

    source = DAG_FILE.read_text(
        encoding="utf-8"
    )

    ast.parse(source)


def test_dag_uses_airflow_sdk() -> None:
    """Airflow 3 public SDK should be used."""

    source = DAG_FILE.read_text(
        encoding="utf-8"
    )

    assert (
        "from airflow.sdk import dag, task"
        in source
    )


def test_dag_contains_required_tasks() -> None:
    """All major pipeline stages must be orchestrated."""

    source = DAG_FILE.read_text(
        encoding="utf-8"
    )

    required_tasks = {
        "preflight",
        "ingest_raw",
        "raw_to_bronze",
        "bronze_to_silver",
        "silver_to_gold",
        "dbt_build",
        "dbt_docs",
        "validate_quality",
    }

    missing = {
        task
        for task in required_tasks
        if f"def {task}(" not in source
    }

    assert not missing


def test_dag_has_operational_controls() -> None:
    """Schedule and concurrency controls should exist."""

    source = DAG_FILE.read_text(
        encoding="utf-8"
    )

    assert 'schedule="@monthly"' in source
    assert "catchup=False" in source
    assert "max_active_runs=1" in source
    assert '"retries": 2' in source
