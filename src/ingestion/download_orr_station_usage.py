"""
RailFlow ORR Station Usage ingestion.

Downloads the official Office of Rail and Road station-usage dataset
into the immutable Raw layer.

Engineering features:
- configuration-driven ingestion
- HTTP retry policy
- atomic download
- SHA-256 checksum
- provenance manifest
- idempotency
- reproducible source metadata
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "data_sources.yaml"


def load_source_config() -> dict[str, Any]:
    """Load the ORR station-usage source configuration."""

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    return config["sources"]["orr_station_usage"]


def sha256_file(path: Path) -> str:
    """Calculate a SHA-256 checksum for a local file."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def build_http_session() -> requests.Session:
    """Create a resilient HTTP session with retry behaviour."""

    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )

    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "User-Agent": (
                "RailFlow-ML-Data-Platform/0.1 "
                "Data Engineering Portfolio Project"
            )
        }
    )

    return session


def download_dataset() -> dict[str, Any]:
    """Download the ORR source file and create an ingestion manifest."""

    config = load_source_config()

    url = config["download_url"]

    destination = PROJECT_ROOT / config["raw_file"]

    manifest_path = PROJECT_ROOT / config["manifest_file"]

    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = destination.with_suffix(".download")

    session = build_http_session()

    print("=" * 72)
    print("RAILFLOW — RAW INGESTION")
    print("=" * 72)
    print(f"Dataset : {config['dataset_name'].strip()}")
    print(f"Publisher: {config['publisher']}")
    print(f"Release : {config['release_period']}")
    print(f"Source  : {url}")
    print()

    with session.get(
        url,
        stream=True,
        timeout=(15, 180),
    ) as response:

        response.raise_for_status()

        with temporary_file.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)

        http_status = response.status_code
        content_type = response.headers.get(
            "content-type",
            "unknown",
        )

    file_size = temporary_file.stat().st_size

    if file_size < 1000:
        temporary_file.unlink(missing_ok=True)

        raise RuntimeError(
            "Downloaded ORR file is unexpectedly small. "
            "Ingestion stopped to protect the Raw layer."
        )

    new_checksum = sha256_file(temporary_file)

    ingestion_status = "downloaded"

    if destination.exists():

        existing_checksum = sha256_file(destination)

        if existing_checksum == new_checksum:

            ingestion_status = "unchanged"

            temporary_file.unlink()

        else:

            temporary_file.replace(destination)

            ingestion_status = "updated"

    else:

        temporary_file.replace(destination)

    final_checksum = sha256_file(destination)

    manifest = {
        "dataset_id": config["dataset_id"],
        "publisher": config["publisher"],
        "dataset_name": config["dataset_name"].strip(),
        "release_period": config["release_period"],
        "source_url": url,
        "raw_file": str(
            destination.relative_to(PROJECT_ROOT)
        ).replace("\\", "/"),
        "downloaded_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "http_status": http_status,
        "content_type": content_type,
        "file_size_bytes": destination.stat().st_size,
        "sha256": final_checksum,
        "ingestion_status": ingestion_status,
    }

    with manifest_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            manifest,
            file,
            indent=2,
        )

    print(f"Raw file       : {destination}")
    print(f"File size      : {destination.stat().st_size:,} bytes")
    print(f"SHA-256        : {final_checksum}")
    print(f"Status         : {ingestion_status}")
    print(f"Manifest       : {manifest_path}")

    print()
    print("=" * 72)
    print("RAW INGESTION: PASS")
    print("=" * 72)

    return manifest


if __name__ == "__main__":
    download_dataset()
