"""Basic RailFlow project smoke tests."""

import sys
from pathlib import Path

# test_project_setup.py:
# railflow-ml-data-platform/tests/unit/test_project_setup.py
#
# parents[0] -> tests/unit
# parents[1] -> tests
# parents[2] -> railflow-ml-data-platform
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_required_directories_exist() -> None:
    """Confirm that the core RailFlow architecture exists."""

    required_directories = [
        "src",
        "data/raw",
        "data/bronze",
        "data/silver",
        "data/gold",
        "spark/jobs",
        "airflow/dags",
        "dbt/models",
        "feature_store",
        "ml/training",
        "infrastructure/terraform",
    ]

    missing_directories = [
        directory for directory in required_directories if not (PROJECT_ROOT / directory).exists()
    ]

    assert not missing_directories, "Required RailFlow directories are missing: " + ", ".join(
        missing_directories
    )


def test_python_version() -> None:
    """RailFlow development environment must use Python 3.12."""

    assert sys.version_info.major == 3
    assert sys.version_info.minor == 12


def test_project_root_exists() -> None:
    """Confirm the test resolves the actual repository root."""

    assert (PROJECT_ROOT / "README.md").exists()
    assert (PROJECT_ROOT / "pyproject.toml").exists()
    assert (PROJECT_ROOT / "requirements.txt").exists()
