from __future__ import annotations

import json
from pathlib import Path

import mlflow
from ml.train_station_interchange_model import (
    load_config,
)
from mlflow import MlflowClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def configure_mlflow(
    config: dict,
) -> str:
    tracking_db = PROJECT_ROOT / config["mlflow"]["tracking_db"]

    tracking_uri = "sqlite:///" + tracking_db.resolve().as_posix()

    mlflow.set_tracking_uri(tracking_uri)

    mlflow.set_registry_uri(tracking_uri)

    return tracking_uri


def main() -> None:
    config = load_config()

    tracking_uri = configure_mlflow(config)

    model_name = config["mlflow"]["registered_model_name"]

    alias = config["mlflow"]["champion_alias"]

    champion_path = PROJECT_ROOT / config["outputs"]["champion_json"]

    champion = json.loads(champion_path.read_text(encoding="utf-8"))

    client = MlflowClient()

    version = client.get_model_version_by_alias(
        model_name,
        alias,
    )

    registry_version = str(version.version)

    metadata_version = str(champion["registered_model_version"])

    if registry_version != metadata_version:
        raise RuntimeError("Registry version does not match champion metadata.")

    if champion["registered_model_name"] != model_name:
        raise RuntimeError("Registered model name mismatch.")

    if champion["alias"] != alias:
        raise RuntimeError("Champion alias mismatch.")

    validation_status = version.tags.get("validation_status")

    if validation_status != "approved":
        raise RuntimeError("Champion is not approved.")

    report = {
        "status": "pass",
        "tracking_uri": tracking_uri,
        "registered_model_name": model_name,
        "alias": alias,
        "version": registry_version,
        "validation_status": validation_status,
        "run_id": version.run_id,
        "dataset_sha256": (champion["dataset_sha256"]),
    }

    output = PROJECT_ROOT / "reports" / "ml" / "airflow_registry_validation.json"

    output.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 72)
    print("MLFLOW REGISTRY VALIDATION")
    print("=" * 72)
    print("Model   :", model_name)
    print("Version :", registry_version)
    print("Alias   :", alias)
    print("Approval:", validation_status)
    print("REGISTRY VALIDATION: PASS")


if __name__ == "__main__":
    main()
