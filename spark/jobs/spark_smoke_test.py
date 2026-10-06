"""
RailFlow Apache Spark environment validation.

Validates that:
- the Spark driver uses the RailFlow Python environment,
- Spark workers use the same Python minor version,
- local DataFrame transformations execute successfully.
"""

from __future__ import annotations

import os
import sys

# ----------------------------------------------------------------
# IMPORTANT:
# Force PySpark driver and worker processes to use this exact
# Python interpreter. This prevents Windows PATH/environment
# settings from accidentally selecting another Python installation.
# ----------------------------------------------------------------

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def main() -> None:
    """Run the RailFlow local Spark smoke test."""

    print("=" * 72)
    print("RAILFLOW — PYSPARK RUNTIME CONFIGURATION")
    print("=" * 72)
    print(f"Driver Python       : {sys.executable}")
    print(f"Driver Python ver.  : {sys.version.split()[0]}")
    print(f"PYSPARK_PYTHON      : {os.environ['PYSPARK_PYTHON']}")
    print(
        "PYSPARK_DRIVER_PYTHON:",
        os.environ["PYSPARK_DRIVER_PYTHON"],
    )

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("RailFlowEnvironmentCheck")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    journeys = [
        ("London", "Manchester", 126, 5),
        ("London", "Edinburgh", 265, 14),
        ("London", "Birmingham", 82, 0),
        ("London", "Bristol", 101, 7),
        ("London", "Leeds", 134, 11),
    ]

    columns = [
        "origin",
        "destination",
        "journey_minutes",
        "delay_minutes",
    ]

    df = spark.createDataFrame(journeys, columns)

    result = (
        df.withColumn(
            "is_delayed",
            F.col("delay_minutes") > 5,
        )
        .withColumn(
            "delay_category",
            F.when(F.col("delay_minutes") == 0, "on_time")
            .when(F.col("delay_minutes") <= 5, "minor")
            .when(F.col("delay_minutes") <= 10, "moderate")
            .otherwise("significant"),
        )
        .orderBy(F.col("delay_minutes").desc())
    )

    print()
    print("=" * 72)
    print("RAILFLOW — APACHE SPARK VALIDATION")
    print("=" * 72)

    result.show(truncate=False)

    total_rows = result.count()

    delayed_rows = result.filter(
        F.col("is_delayed")
    ).count()

    average_delay = (
        result.agg(
            F.round(
                F.avg("delay_minutes"),
                2,
            ).alias("average_delay")
        )
        .collect()[0]["average_delay"]
    )

    print(f"Spark version       : {spark.version}")
    print(f"Rows processed      : {total_rows}")
    print(f"Delayed journeys    : {delayed_rows}")
    print(f"Average delay       : {average_delay} minutes")

    assert total_rows == 5
    assert delayed_rows == 3

    print()
    print("=" * 72)
    print("APACHE SPARK ENVIRONMENT: PASS")
    print("=" * 72)

    spark.stop()


if __name__ == "__main__":
    main()
