"""RailFlow end-to-end orchestration DAG."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.sdk import dag, task

PROJECT_ROOT = Path(
    os.environ.get(
        "RAILFLOW_PROJECT_ROOT",
        "/opt/airflow/railflow",
    )
)

RAILFLOW_PYTHON = os.environ.get(
    "RAILFLOW_PYTHON",
    "/opt/railflow-venv/bin/python",
)

RAILFLOW_DBT = os.environ.get(
    "RAILFLOW_DBT",
    "/opt/railflow-venv/bin/dbt",
)

DBT_PROJECT = PROJECT_ROOT / "dbt"

DBT_PROFILES = (
    DBT_PROJECT
    / "profiles"
)

QUALITY_ROOT = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "orr"
    / "station_usage"
)


def run_command(
    command: list[str],
    environment: dict[str, str] | None = None,
) -> None:
    """Run a RailFlow subprocess."""

    env = os.environ.copy()

    if environment:
        env.update(environment)

    print(
        "Executing:",
        " ".join(command),
    )

    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


@dag(
    dag_id="railflow_end_to_end",
    description=(
        "ORR ingestion through Spark Medallion layers, "
        "dbt marts and ML feature validation."
    ),
    schedule="@monthly",
    start_date=datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    ),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "railflow-data-engineering",
        "retries": 2,
        "retry_delay": timedelta(
            minutes=5
        ),
    },
    tags=[
        "railflow",
        "spark",
        "dbt",
        "ml",
        "orr",
    ],
)
def railflow_end_to_end():
    """Build the complete RailFlow DAG."""

    @task(
        execution_timeout=timedelta(
            minutes=5
        )
    )
    def preflight() -> None:
        """Validate pipeline components."""

        required = [
            (
                PROJECT_ROOT
                / "src"
                / "ingestion"
                / "download_orr_station_usage.py"
            ),
            (
                PROJECT_ROOT
                / "spark"
                / "jobs"
                / "orr_station_usage_raw_to_bronze.py"
            ),
            (
                PROJECT_ROOT
                / "spark"
                / "jobs"
                / "orr_station_usage_bronze_to_silver.py"
            ),
            (
                PROJECT_ROOT
                / "spark"
                / "jobs"
                / "orr_station_usage_silver_to_gold.py"
            ),
            (
                DBT_PROJECT
                / "dbt_project.yml"
            ),
        ]

        missing = [
            str(path)
            for path in required
            if not path.exists()
        ]

        if missing:
            raise RuntimeError(
                "Missing RailFlow components: "
                + ", ".join(missing)
            )

        run_command(
            [
                RAILFLOW_PYTHON,
                "--version",
            ]
        )

        run_command(
            [
                RAILFLOW_DBT,
                "--version",
            ]
        )

    @task(
        execution_timeout=timedelta(
            minutes=10
        )
    )
    def ingest_raw() -> None:
        """Download official ORR data."""

        run_command(
            [
                RAILFLOW_PYTHON,
                (
                    "src/ingestion/"
                    "download_orr_station_usage.py"
                ),
            ]
        )

    @task(
        execution_timeout=timedelta(
            minutes=20
        )
    )
    def raw_to_bronze() -> None:
        """Run Raw to Bronze Spark transformation."""

        run_command(
            [
                RAILFLOW_PYTHON,
                (
                    "spark/jobs/"
                    "orr_station_usage_raw_to_bronze.py"
                ),
            ],
            {
                "PYSPARK_PYTHON": (
                    RAILFLOW_PYTHON
                ),
                "PYSPARK_DRIVER_PYTHON": (
                    RAILFLOW_PYTHON
                ),
            },
        )

    @task(
        execution_timeout=timedelta(
            minutes=20
        )
    )
    def bronze_to_silver() -> None:
        """Run Bronze to Silver transformation."""

        run_command(
            [
                RAILFLOW_PYTHON,
                (
                    "spark/jobs/"
                    "orr_station_usage_bronze_to_silver.py"
                ),
            ],
            {
                "PYSPARK_PYTHON": (
                    RAILFLOW_PYTHON
                ),
                "PYSPARK_DRIVER_PYTHON": (
                    RAILFLOW_PYTHON
                ),
            },
        )

    @task(
        execution_timeout=timedelta(
            minutes=30
        )
    )
    def silver_to_gold() -> None:
        """Create Gold marts and ML features."""

        run_command(
            [
                RAILFLOW_PYTHON,
                (
                    "spark/jobs/"
                    "orr_station_usage_silver_to_gold.py"
                ),
            ],
            {
                "PYSPARK_PYTHON": (
                    RAILFLOW_PYTHON
                ),
                "PYSPARK_DRIVER_PYTHON": (
                    RAILFLOW_PYTHON
                ),
            },
        )

    @task(
        execution_timeout=timedelta(
            minutes=20
        )
    )
    def dbt_build() -> None:
        """Build and test dbt models."""

        duckdb_path = (
            DBT_PROJECT
            / "railflow_analytics.duckdb"
        )

        run_command(
            [
                RAILFLOW_DBT,
                "build",
                "--project-dir",
                str(DBT_PROJECT),
                "--profiles-dir",
                str(DBT_PROFILES),
            ],
            {
                "RAILFLOW_PROJECT_ROOT": (
                    str(PROJECT_ROOT)
                ),
                "RAILFLOW_DUCKDB_PATH": (
                    str(duckdb_path)
                ),
            },
        )

    @task(
        execution_timeout=timedelta(
            minutes=10
        )
    )
    def dbt_docs() -> None:
        """Generate dbt documentation."""

        duckdb_path = (
            DBT_PROJECT
            / "railflow_analytics.duckdb"
        )

        run_command(
            [
                RAILFLOW_DBT,
                "docs",
                "generate",
                "--project-dir",
                str(DBT_PROJECT),
                "--profiles-dir",
                str(DBT_PROFILES),
            ],
            {
                "RAILFLOW_PROJECT_ROOT": (
                    str(PROJECT_ROOT)
                ),
                "RAILFLOW_DUCKDB_PATH": (
                    str(duckdb_path)
                ),
            },
        )

    @task(
        execution_timeout=timedelta(
            minutes=5
        )
    )
    def validate_quality() -> None:

        def extract_result(value):
            if isinstance(value, bool):
                return value

            if isinstance(value, str):
                value = value.strip().lower()

                if value in {
                    "pass",
                    "passed",
                    "success",
                    "successful",
                    "ok",
                    "true",
                    "valid",
                }:
                    return True

                if value in {
                    "fail",
                    "failed",
                    "failure",
                    "false",
                    "invalid",
                    "error",
                }:
                    return False

                return None

            if isinstance(value, dict):

                for key in (
                    "passed",
                    "pass",
                    "success",
                    "successful",
                    "ok",
                    "valid",
                    "result",
                    "status",
                ):
                    if key in value:
                        result = extract_result(value[key])

                        if result is not None:
                            return result

                boolean_values = [
                    item
                    for item in value.values()
                    if isinstance(item, bool)
                ]

                if len(boolean_values) == 1:
                    return boolean_values[0]

            return None

        reports = {
            "bronze": QUALITY_ROOT / "bronze_quality_report.json",
            "silver": QUALITY_ROOT / "silver_quality_report.json",
            "gold": QUALITY_ROOT / "gold_quality_report.json",
        }

        for stage, report_path in reports.items():

            if not report_path.exists():
                raise RuntimeError(
                    f"{stage} quality report missing: {report_path}"
                )

            with report_path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                report = json.load(handle)

            checks = report.get("quality_checks")

            if not isinstance(checks, dict):
                raise RuntimeError(
                    f"{stage} quality report has no valid quality_checks object"
                )

            if not checks:
                raise RuntimeError(
                    f"{stage} quality report contains no quality checks"
                )

            failed_checks = []
            unknown_checks = []

            for check_name, check_value in checks.items():

                result = extract_result(check_value)

                if result is False:
                    failed_checks.append(check_name)

                elif result is None:
                    unknown_checks.append(check_name)

            if failed_checks:
                raise RuntimeError(
                    f"{stage} quality failure: "
                    + ", ".join(failed_checks)
                )

            if unknown_checks:
                raise RuntimeError(
                    f"{stage} quality checks use an unrecognised format: "
                    + ", ".join(unknown_checks)
                )

            print(
                f"QUALITY PASS [{stage.upper()}]: "
                f"{len(checks)} checks"
            )

        print("ALL PIPELINE QUALITY GATES: PASS")

    preflight_task = preflight()
    raw_task = ingest_raw()
    bronze_task = raw_to_bronze()
    silver_task = bronze_to_silver()
    gold_task = silver_to_gold()
    dbt_task = dbt_build()
    docs_task = dbt_docs()
    quality_task = validate_quality()

    (
        preflight_task
        >> raw_task
        >> bronze_task
        >> silver_task
        >> gold_task
        >> dbt_task
        >> docs_task
        >> quality_task
    )


railflow_end_to_end()
