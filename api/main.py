from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd
import skops.io as sio
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import mlflow
from mlflow import MlflowClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = PROJECT_ROOT / "config" / "ml_training.yaml"

MANIFEST_PATH = PROJECT_ROOT / "reports" / "ml" / "deployment_manifest.json"


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return yaml.safe_load(handle)


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise RuntimeError("Deployment manifest is missing.")

    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


CONFIG = load_config()

FEATURE_COLUMNS = list(CONFIG["data"]["features"])

MODEL_NAME = CONFIG["mlflow"]["registered_model_name"]

MODEL_ALIAS = CONFIG["mlflow"]["champion_alias"]

TARGET_COLUMN = CONFIG["data"]["target"]["column"]


def configure_mlflow() -> str:
    tracking_db = PROJECT_ROOT / CONFIG["mlflow"]["tracking_db"]

    tracking_uri = "sqlite:///" + tracking_db.resolve().as_posix()

    mlflow.set_tracking_uri(tracking_uri)

    mlflow.set_registry_uri(tracking_uri)

    return tracking_uri


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    c1: float = Field(ge=0)
    c2: float = Field(ge=0)
    c3: float = Field(ge=0)
    c4: float = Field(ge=0)
    c8: float = Field(ge=0)


class PredictionResponse(BaseModel):
    predicted_annual_interchanges: float
    predicted_annual_interchanges_rounded: int
    model_name: str
    model_version: str
    model_alias: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: str
    model_alias: str


class ModelResponse(BaseModel):
    registered_model_name: str
    alias: str
    version: str
    validation_status: str
    model_uri: str
    features: list[str]
    target: str


class ModelRuntime:
    def __init__(self) -> None:
        self._model: Any | None = None
        self._model_version: Any | None = None
        self._lock = Lock()

    @property
    def model_uri(self) -> str:
        return f"models:/{MODEL_NAME}@{MODEL_ALIAS}"

    def load(self) -> tuple[Any, Any]:
        if self._model is not None and self._model_version is not None:
            return (
                self._model,
                self._model_version,
            )

        with self._lock:
            if self._model is not None and self._model_version is not None:
                return (
                    self._model,
                    self._model_version,
                )

            configure_mlflow()

            client = MlflowClient()

            model_version = client.get_model_version_by_alias(
                MODEL_NAME,
                MODEL_ALIAS,
            )

            validation_status = model_version.tags.get("validation_status")

            if validation_status != "approved":
                raise RuntimeError("Registry champion is not approved for serving.")

            manifest = load_manifest()

            if manifest["registered_model_name"] != MODEL_NAME:
                raise RuntimeError("Deployment manifest model name mismatch.")

            if str(manifest["registered_model_version"]) != str(model_version.version):
                raise RuntimeError("Deployment artifact does not match registry champion.")

            if manifest["registry_alias"] != MODEL_ALIAS:
                raise RuntimeError("Deployment manifest alias mismatch.")

            if manifest["feature_columns"] != FEATURE_COLUMNS:
                raise RuntimeError("Serving feature contract mismatch.")

            artifact_path = PROJECT_ROOT / manifest["artifact_path"]

            if not artifact_path.exists():
                raise RuntimeError("Deployment model artifact is missing.")

            actual_sha256 = sha256_file(artifact_path)

            if actual_sha256 != manifest["artifact_sha256"]:
                raise RuntimeError("Deployment model checksum verification failed.")

            unknown_types = set(sio.get_untrusted_types(file=artifact_path))

            trusted_types = set(manifest["trusted_types"])

            if unknown_types != trusted_types:
                raise RuntimeError("Persisted model type allow-list has changed.")

            model = sio.load(
                artifact_path,
                trusted=sorted(trusted_types),
            )

            self._model = model
            self._model_version = model_version

            return (
                self._model,
                self._model_version,
            )

    def predict(
        self,
        payload: PredictionRequest,
    ) -> tuple[float, str]:
        model, model_version = self.load()

        payload_dict = payload.model_dump()

        row = pd.DataFrame(
            [{column: (payload_dict[column]) for column in FEATURE_COLUMNS}],
            columns=FEATURE_COLUMNS,
        )

        predictions = model.predict(row)

        if len(predictions) != 1:
            raise RuntimeError("Unexpected prediction shape.")

        prediction = float(predictions[0])

        if not math.isfinite(prediction):
            raise RuntimeError("Model returned a non-finite prediction.")

        prediction = max(
            0.0,
            prediction,
        )

        return (
            prediction,
            str(model_version.version),
        )


runtime = ModelRuntime()

app = FastAPI(
    title="RailFlow ML Inference API",
    version="1.0.0",
    description=(
        "Production-style inference service for the RailFlow station interchange champion."
    ),
)


@app.get(
    "/health",
    response_model=HealthResponse,
)
def health() -> HealthResponse:
    try:
        runtime.load()

        return HealthResponse(
            status="ok",
            model_loaded=True,
            model_name=MODEL_NAME,
            model_alias=MODEL_ALIAS,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(f"Model service unavailable: {exc}"),
        ) from exc


@app.get(
    "/model",
    response_model=ModelResponse,
)
def model_info() -> ModelResponse:
    try:
        _, model_version = runtime.load()

        return ModelResponse(
            registered_model_name=(MODEL_NAME),
            alias=MODEL_ALIAS,
            version=str(model_version.version),
            validation_status=(
                model_version.tags.get(
                    "validation_status",
                    "unknown",
                )
            ),
            model_uri=(runtime.model_uri),
            features=FEATURE_COLUMNS,
            target=TARGET_COLUMN,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(f"Unable to resolve champion model: {exc}"),
        ) from exc


@app.post(
    "/predict",
    response_model=PredictionResponse,
)
def predict(
    payload: PredictionRequest,
) -> PredictionResponse:
    try:
        prediction, version = runtime.predict(payload)

        return PredictionResponse(
            predicted_annual_interchanges=(prediction),
            predicted_annual_interchanges_rounded=(int(round(prediction))),
            model_name=MODEL_NAME,
            model_version=version,
            model_alias=MODEL_ALIAS,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(f"Prediction service unavailable: {exc}"),
        ) from exc
