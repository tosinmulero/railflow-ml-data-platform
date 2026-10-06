"""
RailFlow ML Data Platform
Local development environment validation.

This script verifies the core Python/data-engineering dependencies
required by the project.
"""

from __future__ import annotations

import platform
import sys

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyspark
import sklearn
import sqlalchemy
import xgboost


def main() -> None:
    """Print the RailFlow development environment configuration."""

    print("=" * 68)
    print("RAILFLOW ML DATA PLATFORM — ENVIRONMENT VALIDATION")
    print("=" * 68)

    versions = {
        "Operating System": platform.platform(),
        "Python": sys.version.split()[0],
        "PySpark": pyspark.__version__,
        "Pandas": pd.__version__,
        "NumPy": np.__version__,
        "PyArrow": pa.__version__,
        "DuckDB": duckdb.__version__,
        "SQLAlchemy": sqlalchemy.__version__,
        "Scikit-learn": sklearn.__version__,
        "XGBoost": xgboost.__version__,
    }

    for component, version in versions.items():
        print(f"{component:<20}: {version}")

    print("=" * 68)
    print("CORE PYTHON ENVIRONMENT: PASS")
    print("=" * 68)


if __name__ == "__main__":
    main()
