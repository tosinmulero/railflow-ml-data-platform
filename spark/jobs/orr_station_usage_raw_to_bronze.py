"""
RailFlow Raw → Bronze transformation.

Reads the official ORR station-usage CSV from the Raw layer and creates
a standardised Parquet Bronze dataset.

Engineering features:
- PySpark transformation
- canonical field names
- metadata columns
- row-level SHA-256 hashes
- schema capture
- data-quality metrics
- Parquet storage
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------
# Spark must use the same Python environment for driver and workers.
# ---------------------------------------------------------------------

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "data_sources.yaml"


def load_source_config() -> dict[str, Any]:
    """Load ORR station-usage configuration."""

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    return config["sources"]["orr_station_usage"]


def canonicalise_column_name(column: str) -> str:
    """Convert raw source column names to analytics-safe snake_case."""

    column = column.strip().lower()

    column = column.replace("&", " and ")

    column = re.sub(
        r"[^a-z0-9]+",
        "_",
        column,
    )

    column = re.sub(
        r"_+",
        "_",
        column,
    )

    return column.strip("_") or "unnamed_column"


def canonicalise_columns(df: DataFrame) -> DataFrame:
    """Standardise and de-duplicate source column names."""

    seen: dict[str, int] = {}

    new_columns: list[str] = []

    for original in df.columns:

        base = canonicalise_column_name(original)

        occurrence = seen.get(base, 0) + 1

        seen[base] = occurrence

        if occurrence == 1:
            new_name = base
        else:
            new_name = f"{base}_{occurrence}"

        new_columns.append(new_name)

    return df.toDF(*new_columns)


def trim_string_columns(df: DataFrame) -> DataFrame:
    """Trim whitespace from all string columns."""

    for field in df.schema.fields:

        if field.dataType.simpleString() == "string":

            df = df.withColumn(
                field.name,
                F.trim(F.col(field.name)),
            )

    return df


def create_quality_report(
    df: DataFrame,
    output_path: Path,
    run_id: str,
) -> dict[str, Any]:
    """Produce Bronze-level quality metrics."""

    row_count = df.count()

    column_count = len(df.columns)

    null_expressions = []

    for column in df.columns:

        null_expressions.append(
            F.sum(
                F.when(
                    F.col(column).isNull()
                    | (
                        F.trim(
                            F.col(column).cast("string")
                        )
                        == ""
                    ),
                    1,
                ).otherwise(0)
            ).alias(column)
        )

    null_counts = (
        df.agg(*null_expressions)
        .collect()[0]
        .asDict()
    )

    exact_duplicate_rows = (
        row_count - df.dropDuplicates().count()
    )

    report = {
        "pipeline": "orr_station_usage_raw_to_bronze",
        "run_id": run_id,
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "row_count": row_count,
        "column_count": column_count,
        "exact_duplicate_rows": exact_duplicate_rows,
        "null_counts": null_counts,
        "columns": df.columns,
        "quality_checks": {
            "minimum_expected_rows": {
                "threshold": 2000,
                "actual": row_count,
                "passed": row_count >= 2000,
            },
            "dataset_not_empty": {
                "passed": row_count > 0,
            },
            "has_columns": {
                "passed": column_count > 0,
            },
        },
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
        )

    return report


def main() -> None:
    """Execute the Raw → Bronze transformation."""

    config = load_source_config()

    raw_file = PROJECT_ROOT / config["raw_file"]

    bronze_path = PROJECT_ROOT / config["bronze_path"]

    quality_path = PROJECT_ROOT / config["quality_report"]

    schema_path = PROJECT_ROOT / config["schema_file"]

    if not raw_file.exists():
        raise FileNotFoundError(
            f"Raw source file does not exist: {raw_file}"
        )

    run_id = str(uuid.uuid4())

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("RailFlowORRRawToBronze")
        .config(
            "spark.sql.shuffle.partitions",
            "4",
        )
        .config(
            "spark.ui.enabled",
            "false",
        )
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    print("=" * 72)
    print("RAILFLOW — RAW → BRONZE")
    print("=" * 72)
    print(f"Run ID     : {run_id}")
    print(f"Raw source : {raw_file}")
    print(f"Bronze     : {bronze_path}")
    print()

    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .option("mode", "PERMISSIVE")
        .option("multiLine", True)
        .option("quote", '"')
        .option("escape", '"')
        .csv(str(raw_file))
    )

    print("Raw rows:", df.count())
    print("Raw columns:", len(df.columns))

    df = canonicalise_columns(df)

    df = trim_string_columns(df)

    source_columns = list(df.columns)

    hash_fields = [
        F.coalesce(
            F.col(column).cast("string"),
            F.lit(""),
        )
        for column in source_columns
    ]

    df = (
        df
        .withColumn(
            "_record_hash",
            F.sha2(
                F.concat_ws(
                    "||",
                    *hash_fields,
                ),
                256,
            ),
        )
        .withColumn(
            "_source_system",
            F.lit("office_of_rail_and_road"),
        )
        .withColumn(
            "_source_dataset",
            F.lit(config["dataset_id"]),
        )
        .withColumn(
            "_source_release",
            F.lit(config["release_period"]),
        )
        .withColumn(
            "_ingestion_run_id",
            F.lit(run_id),
        )
        .withColumn(
            "_ingested_at_utc",
            F.current_timestamp(),
        )
        .withColumn(
            "_source_file",
            F.input_file_name(),
        )
    )

    quality_report = create_quality_report(
        df=df,
        output_path=quality_path,
        run_id=run_id,
    )

    if not quality_report[
        "quality_checks"
    ]["minimum_expected_rows"]["passed"]:

        spark.stop()

        raise RuntimeError(
            "Bronze quality gate failed: "
            "dataset contains fewer than 2,000 rows."
        )

    schema_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with schema_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            df.schema.jsonValue(),
            file,
            indent=2,
        )

    (
        df.write
        .mode("overwrite")
        .option("compression", "snappy")
        .parquet(str(bronze_path))
    )

    bronze_rows = (
        spark.read
        .parquet(str(bronze_path))
        .count()
    )

    if bronze_rows != quality_report["row_count"]:

        spark.stop()

        raise RuntimeError(
            "Bronze reconciliation failed. "
            f"Input rows={quality_report['row_count']}, "
            f"Bronze rows={bronze_rows}"
        )

    print()
    print("=" * 72)
    print("BRONZE DATA SAMPLE")
    print("=" * 72)

    df.show(
        5,
        truncate=30,
        vertical=False,
    )

    print()
    print("Bronze rows       :", bronze_rows)
    print("Bronze columns    :", len(df.columns))
    print(
        "Exact duplicates  :",
        quality_report["exact_duplicate_rows"],
    )
    print("Quality report    :", quality_path)
    print("Schema            :", schema_path)

    print()
    print("=" * 72)
    print("RAW → BRONZE PIPELINE: PASS")
    print("=" * 72)

    spark.stop()


if __name__ == "__main__":
    main()
