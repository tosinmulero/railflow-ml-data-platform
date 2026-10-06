"""RailFlow Bronze layer validation."""

from __future__ import annotations

from pyspark.sql import SparkSession

BRONZE_PATH = (
    "/workspace/data/bronze/orr/"
    "station_usage/release=2024_25"
)


def main() -> None:
    """Validate persisted Bronze Parquet data."""

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("RailFlowBronzeReadBack")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    df = spark.read.parquet(BRONZE_PATH)

    row_count = df.count()
    column_count = len(df.columns)

    required_metadata = {
        "_record_hash",
        "_source_system",
        "_source_dataset",
        "_source_release",
        "_ingestion_run_id",
        "_ingested_at_utc",
        "_source_file",
    }

    missing_metadata = (
        required_metadata
        - set(df.columns)
    )

    print("=" * 72)
    print("RAILFLOW BRONZE READ-BACK")
    print("=" * 72)

    print(f"Rows             : {row_count}")
    print(f"Columns          : {column_count}")
    print(
        "Missing metadata :",
        sorted(missing_metadata),
    )

    print()
    print("Schema:")
    df.printSchema()

    print()
    print("Sample records:")

    df.show(
        5,
        truncate=30,
    )

    assert row_count >= 2000
    assert column_count > 0
    assert not missing_metadata

    print()
    print("=" * 72)
    print("BRONZE READ-BACK: PASS")
    print("=" * 72)

    spark.stop()


if __name__ == "__main__":
    main()
