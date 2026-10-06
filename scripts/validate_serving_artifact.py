from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import skops.io as sio

import mlflow
from ml.train_station_interchange_model import (
    load_config,
    load_training_data,
)
from mlflow import MlflowClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def configure_mlflow(
    config: dict,
) -> None:
    tracking_db = PROJECT_ROOT / config["mlflow"]["tracking_db"]

    uri = "sqlite:///" + tracking_db.resolve().as_posix()

    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)


def main() -> None:
    config = load_config()

    configure_mlflow(config)

    manifest_path = PROJECT_ROOT / "reports" / "ml" / "deployment_manifest.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    model_name = config["mlflow"]["registered_model_name"]

    alias = config["mlflow"]["champion_alias"]

    version = MlflowClient().get_model_version_by_alias(
        model_name,
        alias,
    )

    if str(version.version) != str(manifest["registered_model_version"]):
        raise RuntimeError("Serving artifact version does not match registry champion.")

    artifact_path = PROJECT_ROOT / manifest["artifact_path"]

    if not artifact_path.exists():
        raise RuntimeError("Serving artifact is missing.")

    actual_sha256 = sha256_file(artifact_path)

    if actual_sha256 != manifest["artifact_sha256"]:
        raise RuntimeError("Serving artifact checksum mismatch.")

    unknown_types = set(sio.get_untrusted_types(file=artifact_path))

    trusted_types = set(manifest["trusted_types"])

    if unknown_types != trusted_types:
        raise RuntimeError("Serving artifact type allow-list has changed.")

    model = sio.load(
        artifact_path,
        trusted=sorted(trusted_types),
    )

    dataset, dataset_sha256 = load_training_data(config)

    if dataset_sha256 != manifest["dataset_sha256"]:
        raise RuntimeError("Serving artifact dataset fingerprint mismatch.")

    features = manifest["feature_columns"]

    sample = dataset[features].head(25).copy()

    predictions = np.asarray(
        model.predict(sample),
        dtype=float,
    )

    if len(predictions) != len(sample):
        raise RuntimeError("Unexpected prediction count.")

    if not np.isfinite(predictions).all():
        raise RuntimeError("Serving model returned non-finite predictions.")

    if (predictions < 0).any():
        raise RuntimeError("Serving model returned negative predictions.")

    report = {
        "status": "pass",
        "registered_model_name": model_name,
        "alias": alias,
        "version": str(version.version),
        "artifact_path": str(artifact_path),
        "artifact_sha256": actual_sha256,
        "dataset_sha256": dataset_sha256,
        "prediction_rows": int(len(predictions)),
        "all_predictions_finite": True,
        "all_predictions_nonnegative": True,
    }

    output = PROJECT_ROOT / "reports" / "ml" / "airflow_serving_validation.json"

    output.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 72)
    print("SERVING ARTIFACT VALIDATION")
    print("=" * 72)
    print("Version     :", version.version)
    print("SHA-256     :", actual_sha256)
    print("Sample rows :", len(predictions))
    print("SERVING VALIDATION: PASS")


if __name__ == "__main__":
    main()
