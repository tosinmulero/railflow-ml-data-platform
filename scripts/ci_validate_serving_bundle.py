from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import skops.io as sio

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = PROJECT_ROOT / "reports" / "ml" / "deployment_manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def main() -> None:
    if not MANIFEST_PATH.exists():
        raise RuntimeError("Deployment manifest is missing.")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    artifact_path = PROJECT_ROOT / manifest["artifact_path"]

    if not artifact_path.exists():
        raise RuntimeError(f"Deployment artifact missing: {artifact_path}")

    actual_sha256 = sha256_file(artifact_path)

    expected_sha256 = manifest["artifact_sha256"]

    if actual_sha256 != expected_sha256:
        raise RuntimeError("Deployment artifact SHA-256 does not match manifest.")

    unknown_types = set(sio.get_untrusted_types(file=artifact_path))

    trusted_types = set(manifest["trusted_types"])

    if unknown_types != trusted_types:
        raise RuntimeError("Deployment artifact type allow-list mismatch.")

    model = sio.load(
        artifact_path,
        trusted=sorted(trusted_types),
    )

    features = manifest["feature_columns"]

    if not features:
        raise RuntimeError("Serving feature contract is empty.")

    sample = pd.DataFrame(
        [{feature: 100000.0 for feature in features}],
        columns=features,
    )

    prediction = float(model.predict(sample)[0])

    if not math.isfinite(prediction):
        raise RuntimeError("Serving model returned non-finite prediction.")

    if prediction < 0:
        raise RuntimeError("Serving model returned negative prediction.")

    print("=" * 72)
    print("RAILFLOW CI SERVING BUNDLE")
    print("=" * 72)
    print(
        "Model        :",
        manifest["registered_model_name"],
    )
    print(
        "Version      :",
        manifest["registered_model_version"],
    )
    print(
        "Alias        :",
        manifest["registry_alias"],
    )
    print(
        "Artifact     :",
        artifact_path,
    )
    print(
        "SHA-256      :",
        actual_sha256,
    )
    print(
        "Trusted types:",
        sorted(trusted_types),
    )
    print(
        "Prediction   :",
        prediction,
    )
    print("CI SERVING BUNDLE VALIDATION: PASS")


if __name__ == "__main__":
    main()
