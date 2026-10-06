from __future__ import annotations

import json
from pathlib import Path

from ml.train_station_interchange_model import (
    load_config,
    load_training_data,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    config = load_config()

    dataset, dataset_sha256 = load_training_data(config)

    features = list(config["data"]["features"])

    target = config["data"]["target"]["column"]

    required = features + [target]

    missing = [column for column in required if column not in dataset.columns]

    if missing:
        raise RuntimeError(f"Training columns missing: {missing}")

    if dataset.empty:
        raise RuntimeError("Training dataset is empty.")

    report = {
        "status": "pass",
        "rows": int(len(dataset)),
        "feature_columns": features,
        "target_column": target,
        "dataset_sha256": dataset_sha256,
    }

    output = PROJECT_ROOT / "reports" / "ml" / "airflow_preflight.json"

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
    print("ML FEATURE STORE PREFLIGHT")
    print("=" * 72)
    print("Rows       :", len(dataset))
    print("Features   :", features)
    print("Target     :", target)
    print("Dataset SHA:", dataset_sha256)
    print("PREFLIGHT  : PASS")


if __name__ == "__main__":
    main()
