"""Tests for the RailFlow Silver station-usage layer."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG = json.loads(
    (
        PROJECT_ROOT
        / "config"
        / "silver_station_usage.json"
    ).read_text(
        encoding="utf-8"
    )
)


def test_silver_directory_exists() -> None:
    """Silver output directory must exist."""

    path = (
        PROJECT_ROOT
        / CONFIG["silver_path"]
    )

    assert path.exists()
    assert path.is_dir()


def test_silver_contains_parquet() -> None:
    """Silver layer must contain Parquet part files."""

    path = (
        PROJECT_ROOT
        / CONFIG["silver_path"]
    )

    parquet = list(
        path.rglob("*.parquet")
    )

    assert parquet

    assert all(
        file.stat().st_size > 0
        for file in parquet
    )


def test_silver_success_marker() -> None:
    """Spark successful-write marker must exist."""

    marker = (
        PROJECT_ROOT
        / CONFIG["silver_path"]
        / "_SUCCESS"
    )

    assert marker.exists()


def test_silver_quality_report() -> None:
    """All critical Silver quality gates must pass."""

    path = (
        PROJECT_ROOT
        / CONFIG["quality_report"]
    )

    assert path.exists()

    report = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    checks = report[
        "quality_checks"
    ]

    assert report[
        "silver_row_count"
    ] >= 2000

    assert checks[
        "dataset_not_empty"
    ]

    assert checks[
        "minimum_expected_rows"
    ]

    assert checks[
        "row_count_not_increased"
    ]

    assert checks[
        "record_hash_unique"
    ]

    assert checks[
        "station_key_complete"
    ]

    assert checks[
        "persisted_row_reconciliation"
    ]


def test_data_contract_exists() -> None:
    """Silver data contract must describe the persisted schema."""

    path = (
        PROJECT_ROOT
        / CONFIG["data_contract"]
    )

    assert path.exists()

    contract = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert contract[
        "layer"
    ] == "silver"

    assert contract[
        "primary_surrogate_key"
    ] == "station_key"

    assert len(
        contract["fields"]
    ) > 0


def test_silver_schema_exists() -> None:
    """Silver Spark schema must be persisted."""

    path = (
        PROJECT_ROOT
        / CONFIG["schema_file"]
    )

    assert path.exists()

    schema = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert "fields" in schema
    assert schema["fields"]


def test_data_dictionary_exists() -> None:
    """Human-readable data dictionary must exist."""

    path = (
        PROJECT_ROOT
        / CONFIG["data_dictionary"]
    )

    assert path.exists()

    contents = path.read_text(
        encoding="utf-8"
    )

    assert "Silver Data Dictionary" in contents
    assert "station_key" in contents
