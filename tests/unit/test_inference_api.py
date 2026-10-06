from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import (
    FEATURE_COLUMNS,
    MODEL_ALIAS,
    MODEL_NAME,
    app,
    runtime,
)


class FakeModel:
    def predict(self, frame):
        assert list(frame.columns) == (FEATURE_COLUMNS)

        return np.array(
            [12345.67],
            dtype=float,
        )


class FakeModelVersion:
    version = "1"
    tags = {"validation_status": "approved"}


@pytest.fixture(autouse=True)
def fake_runtime(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "_model",
        FakeModel(),
    )

    monkeypatch.setattr(
        runtime,
        "_model_version",
        FakeModelVersion(),
    )


client = TestClient(app)


def valid_payload():
    return {
        "c1": 100000.0,
        "c2": 150000.0,
        "c3": 25000.0,
        "c4": 275000.0,
        "c8": 75000.0,
    }


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["model_loaded"] is True
    assert payload["model_name"] == MODEL_NAME
    assert payload["model_alias"] == MODEL_ALIAS


def test_model_metadata():
    response = client.get("/model")

    assert response.status_code == 200

    payload = response.json()

    assert payload["registered_model_name"] == MODEL_NAME

    assert payload["alias"] == MODEL_ALIAS

    assert payload["version"] == "1"

    assert payload["validation_status"] == "approved"

    assert payload["features"] == FEATURE_COLUMNS


def test_prediction():
    response = client.post(
        "/predict",
        json=valid_payload(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["predicted_annual_interchanges"] == pytest.approx(12345.67)

    assert payload["predicted_annual_interchanges_rounded"] == 12346

    assert payload["model_name"] == MODEL_NAME


def test_negative_feature_rejected():
    payload = valid_payload()
    payload["c1"] = -1

    response = client.post(
        "/predict",
        json=payload,
    )

    assert response.status_code == 422


def test_missing_feature_rejected():
    payload = valid_payload()
    del payload["c8"]

    response = client.post(
        "/predict",
        json=payload,
    )

    assert response.status_code == 422


def test_extra_feature_rejected():
    payload = valid_payload()
    payload["unexpected"] = 123

    response = client.post(
        "/predict",
        json=payload,
    )

    assert response.status_code == 422
