from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
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


def run_module(
    module: str,
) -> None:
    env = os.environ.copy()

    existing_pythonpath = env.get(
        "PYTHONPATH",
        "",
    )

    env["PYTHONPATH"] = (
        str(PROJECT_ROOT) if not existing_pythonpath else (f"{PROJECT_ROOT}:{existing_pythonpath}")
    )

    command = [
        RAILFLOW_PYTHON,
        "-m",
        module,
    ]

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
    dag_id="railflow_ml_lifecycle",
    description=(
        "Dataset-aware RailFlow ML retraining, "
        "registry governance and deployment "
        "artifact validation."
    ),
    schedule=None,
    start_date=datetime(
        2026,
        10,
        6,
        tzinfo=timezone.utc,
    ),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "railflow-ml-engineering",
        "retries": 0,
    },
    tags=[
        "railflow",
        "ml",
        "mlflow",
        "deployment",
    ],
)
def railflow_ml_lifecycle():

    @task
    def feature_store_ready() -> None:
        run_module("scripts.ml_pipeline_preflight")

    @task
    def retrain_if_dataset_changed() -> None:
        run_module("scripts.train_if_needed")

    @task
    def validate_registry_champion() -> None:
        run_module("scripts.validate_registry_champion")

    @task
    def build_serving_artifact() -> None:
        run_module("scripts.build_serving_artifact")

    @task
    def validate_serving_artifact() -> None:
        run_module("scripts.validate_serving_artifact")

    @task
    def deployment_ready() -> dict:
        reports = {}

        for filename in (
            "retraining_decision.json",
            "airflow_registry_validation.json",
            "deployment_manifest.json",
            "airflow_serving_validation.json",
        ):
            path = PROJECT_ROOT / "reports" / "ml" / filename

            if not path.exists():
                raise RuntimeError(f"Missing lifecycle report: {path}")

            reports[filename] = json.loads(path.read_text(encoding="utf-8"))

        summary = {
            "status": "deployment_ready",
            "training_action": (reports["retraining_decision.json"]["action"]),
            "champion_version": (reports["airflow_registry_validation.json"]["version"]),
            "artifact_sha256": (reports["deployment_manifest.json"]["artifact_sha256"]),
        }

        print(
            json.dumps(
                summary,
                indent=2,
            )
        )

        return summary

    preflight = feature_store_ready()

    retraining = retrain_if_dataset_changed()

    registry = validate_registry_champion()

    serving_build = build_serving_artifact()

    serving_validation = validate_serving_artifact()

    ready = deployment_ready()

    (preflight >> retraining >> registry >> serving_build >> serving_validation >> ready)


railflow_ml_lifecycle()
