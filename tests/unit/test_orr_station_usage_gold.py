"""Tests for RailFlow Gold assets."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG = json.loads(
    (
        PROJECT_ROOT
        / "config"
        / "gold_station_usage.json"
    ).read_text(
        encoding="utf-8"
    )
)


def gold_path(key: str) -> Path:
    """Resolve Gold asset path."""

    return (
        PROJECT_ROOT
        / CONFIG[key]
    )


def test_station_mart_exists() -> None:
    """Station mart must contain Parquet output."""

    path = gold_path(
        "station_mart_path"
    )

    assert path.exists()

    assert list(
        path.rglob("*.parquet")
    )

    assert (
        path / "_SUCCESS"
    ).exists()


def test_summary_mart_exists() -> None:
    """Summary mart must contain Parquet output."""

    path = gold_path(
        "summary_mart_path"
    )

    assert path.exists()

    assert list(
        path.rglob("*.parquet")
    )

    assert (
        path / "_SUCCESS"
    ).exists()


def test_feature_table_exists() -> None:
    """ML feature table must contain Parquet output."""

    path = gold_path(
        "feature_table_path"
    )

    assert path.exists()

    assert list(
        path.rglob("*.parquet")
    )

    assert (
        path / "_SUCCESS"
    ).exists()


def test_gold_quality_report() -> None:
    """Critical Gold quality gates must pass."""

    path = gold_path(
        "quality_report"
    )

    report = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    checks = report[
        "quality_checks"
    ]

    assert report[
        "station_mart_row_count"
    ] >= 2000

    assert report[
        "metric_columns"
    ]

    assert report[
        "primary_usage_metric"
    ]

    assert all(
        checks.values()
    )


def test_feature_contract() -> None:
    """ML feature contract must be valid."""

    path = gold_path(
        "feature_contract"
    )

    contract = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert contract[
        "asset_type"
    ] == "ml_feature_table"

    assert contract[
        "primary_entity_key"
    ] == "feature_entity_key"

    assert contract[
        "entity_key"
    ] == "station_key"

    assert contract[
        "source_metrics"
    ]

    assert contract[
        "fields"
    ]


def test_gold_data_dictionary() -> None:
    """Gold layer must be documented."""

    path = gold_path(
        "data_dictionary"
    )

    assert path.exists()

    text = path.read_text(
        encoding="utf-8"
    )

    assert "Gold Layer" in text
    assert "ML Feature Table" in text
