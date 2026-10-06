"""Tests for the RailFlow ORR ingestion pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = PROJECT_ROOT / "config" / "data_sources.yaml"


def load_config() -> dict:
    """Load the station-usage configuration."""

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return yaml.safe_load(file)["sources"]["orr_station_usage"]


def sha256_file(path: Path) -> str:
    """Return file SHA-256 checksum."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def test_data_source_configuration() -> None:
    """Source configuration should contain an HTTPS endpoint."""

    config = load_config()

    assert config["publisher"] == ("Office of Rail and Road")

    assert config["download_url"].startswith("https://")

    assert config["release_period"] == "2024_25"


def test_raw_dataset_exists() -> None:
    """The Raw ORR dataset must exist after ingestion."""

    config = load_config()

    raw_file = PROJECT_ROOT / config["raw_file"]

    assert raw_file.exists()

    assert raw_file.stat().st_size > 1000


def test_raw_manifest_matches_dataset() -> None:
    """Manifest checksum must match the Raw source file."""

    config = load_config()

    raw_file = PROJECT_ROOT / config["raw_file"]

    manifest_file = PROJECT_ROOT / config["manifest_file"]

    assert manifest_file.exists()

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert manifest["sha256"] == sha256_file(raw_file)


def test_bronze_dataset_exists() -> None:
    """Bronze layer must contain Parquet output."""

    config = load_config()

    bronze_path = PROJECT_ROOT / config["bronze_path"]

    parquet_files = list(bronze_path.rglob("*.parquet"))

    assert parquet_files


def test_bronze_quality_report() -> None:
    """Bronze quality gate should pass."""

    config = load_config()

    report_file = PROJECT_ROOT / config["quality_report"]

    assert report_file.exists()

    report = json.loads(report_file.read_text(encoding="utf-8"))

    assert report["row_count"] >= 2000

    assert report["quality_checks"]["minimum_expected_rows"]["passed"]


def test_bronze_schema_capture_exists() -> None:
    """Bronze schema should be captured for observability."""

    config = load_config()

    schema_file = PROJECT_ROOT / config["schema_file"]

    assert schema_file.exists()
