from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import mlflow.pyfunc
import mlflow.sklearn
import numpy as np

import mlflow
from ml.train_station_interchange_model import (
    load_config,
    load_training_data,
)
from mlflow import MlflowClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def project_path(
    relative_path: str,
) -> Path:
    return PROJECT_ROOT / relative_path


def configure_mlflow(
    config: dict[str, Any],
) -> str:
    tracking_db = project_path(config["mlflow"]["tracking_db"])

    tracking_uri = "sqlite:///" + tracking_db.resolve().as_posix()

    mlflow.set_tracking_uri(tracking_uri)

    mlflow.set_registry_uri(tracking_uri)

    return tracking_uri


def main() -> None:
    config = load_config()

    tracking_uri = configure_mlflow(config)

    model_name = config["mlflow"]["registered_model_name"]

    alias = config["mlflow"]["champion_alias"]

    model_uri = f"models:/{model_name}@{alias}"

    client = MlflowClient()

    model_version = client.get_model_version_by_alias(
        model_name,
        alias,
    )

    validation_status = model_version.tags.get("validation_status")

    if validation_status != "approved":
        raise RuntimeError("Champion model does not have validation_status=approved.")

    champion_path = project_path(config["outputs"]["champion_json"])

    if not champion_path.exists():
        raise RuntimeError("champion.json is missing.")

    champion = json.loads(champion_path.read_text(encoding="utf-8"))

    champion_version = str(champion["registered_model_version"])

    registry_version = str(model_version.version)

    if champion_version != registry_version:
        raise RuntimeError(
            "Champion JSON and MLflow "
            "registry version disagree: "
            f"{champion_version} != "
            f"{registry_version}"
        )

    if champion["alias"] != alias:
        raise RuntimeError("Champion alias mismatch.")

    model = mlflow.pyfunc.load_model(model_uri)

    dataset, dataset_sha256 = load_training_data(config)

    expected_sha256 = champion["dataset_sha256"]

    if dataset_sha256 != expected_sha256:
        raise RuntimeError(
            "Current feature dataset does not match champion training dataset fingerprint."
        )

    features = list(config["data"]["features"])

    sample = dataset[features].head(25)

    predictions = np.asarray(
        model.predict(sample),
        dtype=float,
    )

    if len(predictions) != len(sample):
        raise RuntimeError("Prediction row count mismatch.")

    if not np.isfinite(predictions).all():
        raise RuntimeError("Champion produced non-finite predictions.")

    if (predictions < 0).any():
        raise RuntimeError("Champion produced negative interchange predictions.")

    mean_prediction = float(np.mean(predictions))

    if not math.isfinite(mean_prediction):
        raise RuntimeError("Invalid prediction summary.")

    report = {
        "status": "passed",
        "tracking_uri": (tracking_uri),
        "registered_model_name": (model_name),
        "alias": alias,
        "version": registry_version,
        "validation_status": (validation_status),
        "model_uri": model_uri,
        "feature_columns": features,
        "feature_count": len(features),
        "validation_rows": len(sample),
        "predictions_finite": True,
        "predictions_non_negative": True,
        "dataset_sha256": (dataset_sha256),
        "mean_sample_prediction": (mean_prediction),
        "min_sample_prediction": float(np.min(predictions)),
        "max_sample_prediction": float(np.max(predictions)),
    }

    output = project_path("reports/ml/champion_validation.json")

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 72)
    print("RAILFLOW - CHAMPION MODEL VALIDATION")
    print("=" * 72)
    print(f"Model       : {model_name}")
    print(f"Alias       : {alias}")
    print(f"Version     : {registry_version}")
    print(f"Status      : {validation_status}")
    print(f"Features    : {features}")
    print(f"Sample rows : {len(sample)}")
    print(f"Dataset SHA : {dataset_sha256}")
    print("Predictions : finite and non-negative")
    print()
    print("CHAMPION MODEL VALIDATION: PASS")


if __name__ == "__main__":
    main()
