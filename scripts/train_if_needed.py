from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ml.train_station_interchange_model import (
    load_config,
    load_training_data,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    config = load_config()

    _, dataset_sha256 = load_training_data(config)

    champion_path = PROJECT_ROOT / config["outputs"]["champion_json"]

    previous_sha256 = None

    if champion_path.exists():
        champion = json.loads(champion_path.read_text(encoding="utf-8"))

        previous_sha256 = champion.get("dataset_sha256")

    if previous_sha256 == dataset_sha256:
        action = "skipped"

        print("TRAINING SKIPPED: champion already uses current dataset.")

    else:
        action = "trained"

        print("DATASET CHANGE DETECTED.")
        print("Starting candidate training...")

        subprocess.run(
            [
                sys.executable,
                "-m",
                "ml.train_station_interchange_model",
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )

        champion = json.loads(champion_path.read_text(encoding="utf-8"))

        if champion.get("dataset_sha256") != dataset_sha256:
            raise RuntimeError("New champion does not match current dataset fingerprint.")

    report = {
        "status": "pass",
        "action": action,
        "previous_dataset_sha256": (previous_sha256),
        "current_dataset_sha256": (dataset_sha256),
        "evaluated_at_utc": (datetime.now(timezone.utc).isoformat()),
    }

    output = PROJECT_ROOT / "reports" / "ml" / "retraining_decision.json"

    output.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("RETRAINING DECISION")
    print("=" * 72)
    print("Action:", action)
    print("Dataset SHA:", dataset_sha256)
    print("RETRAINING GATE: PASS")


if __name__ == "__main__":
    main()
