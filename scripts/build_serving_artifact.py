from __future__ import annotations

import hashlib
import json
import math
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import skops
import skops.io as sio
from sklearn.model_selection import train_test_split

from ml.train_station_interchange_model import (
    build_model,
    load_config,
    load_training_data,
    regression_metrics,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_UNTRUSTED_TYPES = {
    "numpy.dtype",
    "sklearn.tree._tree.Tree",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def main() -> None:
    config = load_config()

    champion_path = PROJECT_ROOT / config["outputs"]["champion_json"]

    if not champion_path.exists():
        raise RuntimeError("champion.json is missing.")

    champion = json.loads(champion_path.read_text(encoding="utf-8"))

    model_name = champion["model_name"]

    if model_name == "baseline":
        raise RuntimeError("Baseline model cannot be deployed as production champion.")

    if model_name not in config["models"]:
        raise RuntimeError(f"Unknown champion model: {model_name}")

    dataset, dataset_sha256 = load_training_data(config)

    if dataset_sha256 != champion["dataset_sha256"]:
        raise RuntimeError("Training dataset fingerprint does not match champion metadata.")

    features = list(config["data"]["features"])

    target = config["data"]["target"]["column"]

    x = dataset[features].copy()
    y = dataset[target].copy()

    (
        x_train,
        x_test,
        y_train,
        y_test,
    ) = train_test_split(
        x,
        y,
        test_size=config["split"]["test_size"],
        random_state=config["split"]["random_state"],
    )

    print("=" * 72)
    print("RAILFLOW - BUILD SERVING ARTIFACT")
    print("=" * 72)
    print("Champion       :", model_name)
    print(
        "Registry model :",
        champion["registered_model_name"],
    )
    print(
        "Version        :",
        champion["registered_model_version"],
    )
    print(
        "Alias          :",
        champion["alias"],
    )
    print("Training rows  :", len(x_train))
    print("Test rows      :", len(x_test))
    print()

    model = build_model(
        model_name,
        config,
    )

    print("Training deterministic champion...")

    model.fit(
        x_train,
        y_train,
    )

    predictions = np.clip(
        model.predict(x_test),
        0.0,
        None,
    )

    metrics = regression_metrics(
        y_test,
        predictions,
    )

    expected_rmsle = float(champion["rmsle"])

    actual_rmsle = float(metrics["rmsle"])

    print(
        "Expected RMSLE :",
        expected_rmsle,
    )

    print(
        "Actual RMSLE   :",
        actual_rmsle,
    )

    if not math.isclose(
        actual_rmsle,
        expected_rmsle,
        rel_tol=1e-6,
        abs_tol=1e-6,
    ):
        raise RuntimeError("Rebuilt deployment model does not reproduce champion RMSLE.")

    artifact_dir = PROJECT_ROOT / "models" / "deployment"

    artifact_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact_name = (
        f"railflow_station_interchange_regressor_v{champion['registered_model_version']}.skops"
    )

    artifact_path = artifact_dir / artifact_name

    sio.dump(
        model,
        artifact_path,
    )

    unknown_types = set(sio.get_untrusted_types(file=artifact_path))

    print()
    print(
        "Skops untrusted types:",
        sorted(unknown_types),
    )

    unexpected_types = unknown_types - ALLOWED_UNTRUSTED_TYPES

    if unexpected_types:
        raise RuntimeError(
            f"Deployment artifact contains unexpected untrusted types: {sorted(unexpected_types)}"
        )

    trusted_types = sorted(unknown_types)

    loaded_model = sio.load(
        artifact_path,
        trusted=trusted_types,
    )

    validation_sample = x_test.head(25)

    original_predictions = np.asarray(
        model.predict(validation_sample),
        dtype=float,
    )

    loaded_predictions = np.asarray(
        loaded_model.predict(validation_sample),
        dtype=float,
    )

    if not np.allclose(
        original_predictions,
        loaded_predictions,
        rtol=1e-12,
        atol=1e-12,
    ):
        raise RuntimeError("Persisted model predictions do not match in-memory model.")

    artifact_sha256 = sha256_file(artifact_path)

    manifest = {
        "status": "approved",
        "registered_model_name": (champion["registered_model_name"]),
        "registered_model_version": (str(champion["registered_model_version"])),
        "registry_alias": (champion["alias"]),
        "training_run_id": (champion["run_id"]),
        "model_name": model_name,
        "source_mlflow_model_uri": (champion["model_uri"]),
        "artifact_format": "skops",
        "artifact_path": str(artifact_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "artifact_sha256": (artifact_sha256),
        "dataset_sha256": (dataset_sha256),
        "feature_columns": (features),
        "target_column": target,
        "trusted_types": (trusted_types),
        "validation": {
            "rmsle": metrics["rmsle"],
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "r2": metrics["r2"],
            "prediction_equivalence": (True),
        },
        "environment": {
            "python": (platform.python_version()),
            "scikit_learn": (sklearn.__version__),
            "skops": (skops.__version__),
            "pandas": (pd.__version__),
            "numpy": (np.__version__),
        },
    }

    manifest_path = PROJECT_ROOT / "reports" / "ml" / "deployment_manifest.json"

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("DEPLOYMENT ARTIFACT")
    print("=" * 72)

    print(
        "Artifact :",
        artifact_path,
    )

    print(
        "SHA-256  :",
        artifact_sha256,
    )

    print("Format   : skops")

    print(
        "Types    :",
        trusted_types,
    )

    print()
    print("CHAMPION DEPLOYMENT ARTIFACT: PASS")


if __name__ == "__main__":
    main()
