"""
RailFlow Silver -> Gold pipeline.

This version supports ORR business metrics that arrive as either:

- native numeric Spark columns, or
- numeric-looking string columns.

It profiles candidate columns, converts valid station-usage metrics,
and produces analytics marts and an ML feature table.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import NumericType, StringType

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "gold_station_usage.json"
)

NUMERIC_PATTERN = r"^-?[0-9]+(?:\.[0-9]+)?$"


METRIC_HINTS = (
    "entry",
    "entries",
    "exit",
    "exits",
    "interchange",
    "interchanges",
    "usage",
    "passenger",
    "passengers",
    "journey",
    "journeys",
    "footfall",
    "total",
)


EXCLUDED_HINTS = (
    "station_key",
    "code",
    "crs",
    "nlc",
    "easting",
    "northing",
    "latitude",
    "longitude",
    "year_start",
    "year_end",
    "financial_year",
    "rank",
)


PRIMARY_METRIC_PRIORITY = (
    "entries_and_exits",
    "entries_exits",
    "entry_and_exit",
    "entry_exit",
    "total_entries",
    "entries",
    "exits",
    "usage",
    "passenger",
    "journey",
    "interchange",
)


def load_config() -> dict[str, Any]:
    """Load Gold-layer configuration."""

    return json.loads(
        CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )


def is_excluded(name: str) -> bool:
    """Prevent identifiers/geography/year fields becoming ML metrics."""

    lower = name.lower()

    if lower.startswith("_"):
        return True

    return any(
        hint in lower
        for hint in EXCLUDED_HINTS
    )


def has_metric_hint(name: str) -> bool:
    """Check whether a source column looks like a usage metric."""

    lower = name.lower()

    return any(
        hint in lower
        for hint in METRIC_HINTS
    )


def numeric_expression(column: str):
    """Normalise thousands separators and whitespace."""

    return F.regexp_replace(
        F.trim(
            F.col(column)
        ),
        r"[,\s]",
        "",
    )


def numeric_parse_ratio(
    df: DataFrame,
    column: str,
) -> tuple[int, int, float]:
    """Measure whether a string field genuinely contains numbers."""

    populated = (
        df.filter(
            F.col(column).isNotNull()
            & (
                F.trim(
                    F.col(column)
                )
                != ""
            )
        )
        .count()
    )

    if populated == 0:
        return 0, 0, 0.0

    cleaned = numeric_expression(
        column
    )

    parseable = (
        df.filter(
            F.col(column).isNotNull()
            & cleaned.rlike(
                NUMERIC_PATTERN
            )
        )
        .count()
    )

    return (
        populated,
        parseable,
        parseable / populated,
    )


def materialise_business_metrics(
    df: DataFrame,
) -> tuple[
    DataFrame,
    list[str],
    dict[str, Any],
]:
    """
    Discover and strongly type business metrics.

    Metric candidates with semantic usage names are accepted when at
    least 80% of populated values are numeric. A conservative 95%
    numeric fallback is used only when semantic detection finds none.
    """

    metrics: list[str] = []

    profile: dict[str, Any] = {}

    # --------------------------------------------------------------
    # Native numeric columns
    # --------------------------------------------------------------

    for field in df.schema.fields:

        name = field.name

        if is_excluded(name):
            continue

        if (
            isinstance(
                field.dataType,
                NumericType,
            )
            and has_metric_hint(name)
        ):
            metrics.append(name)

            profile[name] = {
                "source_type": (
                    field.dataType.simpleString()
                ),
                "action": "native_numeric",
                "parse_ratio": 1.0,
            }

    # --------------------------------------------------------------
    # Numeric-looking string business metrics
    # --------------------------------------------------------------

    for field in df.schema.fields:

        name = field.name

        if name in metrics:
            continue

        if is_excluded(name):
            continue

        if not isinstance(
            field.dataType,
            StringType,
        ):
            continue

        if not has_metric_hint(name):
            continue

        (
            populated,
            parseable,
            ratio,
        ) = numeric_parse_ratio(
            df,
            name,
        )

        profile[name] = {
            "source_type": "string",
            "populated": populated,
            "parseable": parseable,
            "parse_ratio": ratio,
        }

        if ratio < 0.80:
            profile[name][
                "action"
            ] = "rejected"

            continue

        cleaned = numeric_expression(
            name
        )

        df = df.withColumn(
            name,
            F.when(
                cleaned.rlike(
                    NUMERIC_PATTERN
                ),
                cleaned.cast("double"),
            ).otherwise(
                F.lit(None).cast(
                    "double"
                )
            ),
        )

        metrics.append(name)

        profile[name][
            "action"
        ] = "cast_to_double"

    # --------------------------------------------------------------
    # Defensive fallback
    # --------------------------------------------------------------

    if not metrics:

        for field in df.schema.fields:

            name = field.name

            if is_excluded(name):
                continue

            if not isinstance(
                field.dataType,
                StringType,
            ):
                continue

            (
                populated,
                parseable,
                ratio,
            ) = numeric_parse_ratio(
                df,
                name,
            )

            if (
                populated == 0
                or ratio < 0.95
            ):
                continue

            cleaned = numeric_expression(
                name
            )

            df = df.withColumn(
                name,
                F.when(
                    cleaned.rlike(
                        NUMERIC_PATTERN
                    ),
                    cleaned.cast(
                        "double"
                    ),
                ).otherwise(
                    F.lit(None).cast(
                        "double"
                    )
                ),
            )

            metrics.append(name)

            profile[name] = {
                "source_type": "string",
                "populated": populated,
                "parseable": parseable,
                "parse_ratio": ratio,
                "action": (
                    "fallback_cast_to_double"
                ),
            }

    metrics = list(
        dict.fromkeys(metrics)
    )

    return (
        df,
        metrics,
        profile,
    )


def choose_primary_metric(
    metrics: list[str],
) -> str:
    """Choose the most useful station-usage measure."""

    if not metrics:
        raise RuntimeError(
            "No usable business metrics remained "
            "after numeric profiling."
        )

    for priority in (
        PRIMARY_METRIC_PRIORITY
    ):

        for metric in metrics:

            if priority in metric.lower():
                return metric

    return metrics[0]


def identify_dimensions(
    df: DataFrame,
    metrics: list[str],
) -> list[str]:
    """Return useful descriptive fields."""

    dimensions = []

    for field in df.schema.fields:

        name = field.name

        if name in metrics:
            continue

        if name == "station_key":
            continue

        if name.startswith("_"):
            continue

        if isinstance(
            field.dataType,
            StringType,
        ):
            dimensions.append(name)

    return dimensions


def create_station_mart(
    df: DataFrame,
    dimensions: list[str],
    metrics: list[str],
    primary_metric: str,
) -> DataFrame:
    """Create business-facing station analytics mart."""

    keep = (
        ["station_key"]
        + dimensions
        + metrics
    )

    for column in (
        "financial_year_start",
        "financial_year_end",
        "_record_hash",
        "_source_dataset",
        "_source_release",
    ):

        if (
            column in df.columns
            and column not in keep
        ):
            keep.append(column)

    mart = df.select(
        *keep
    )

    rank_window = Window.orderBy(
        F.col(
            primary_metric
        ).desc_nulls_last()
    )

    return (
        mart
        .withColumn(
            "primary_usage_metric",
            F.lit(primary_metric),
        )
        .withColumn(
            "primary_usage_value",
            F.col(
                primary_metric
            ).cast("double"),
        )
        .withColumn(
            "station_usage_rank",
            F.dense_rank().over(
                rank_window
            ),
        )
        .withColumn(
            "station_usage_percent_rank",
            F.percent_rank().over(
                rank_window
            ),
        )
    )


def create_summary_mart(
    station_mart: DataFrame,
    metrics: list[str],
    primary_metric: str,
) -> DataFrame:
    """Create one-row aggregate mart."""

    expressions = [
        F.count("*").alias(
            "station_record_count"
        ),
        F.countDistinct(
            "station_key"
        ).alias(
            "distinct_station_count"
        ),
    ]

    for metric in metrics:

        expressions.extend(
            [
                F.sum(metric).alias(
                    f"sum__{metric}"
                ),
                F.avg(metric).alias(
                    f"avg__{metric}"
                ),
                F.min(metric).alias(
                    f"min__{metric}"
                ),
                F.max(metric).alias(
                    f"max__{metric}"
                ),
            ]
        )

    return (
        station_mart
        .agg(*expressions)
        .withColumn(
            "primary_usage_metric",
            F.lit(primary_metric),
        )
    )


def create_feature_table(
    station_mart: DataFrame,
    metrics: list[str],
) -> DataFrame:
    """Build reusable machine-learning features."""

    base_columns = [
        "station_key",
    ]

    for column in (
        "financial_year_start",
        "financial_year_end",
        "_record_hash",
        "_source_release",
    ):

        if column in station_mart.columns:
            base_columns.append(column)

    for metric in metrics:

        if metric not in base_columns:
            base_columns.append(metric)

    features = station_mart.select(
        *base_columns
    )

    # Use source row lineage where possible.
    if "_record_hash" in features.columns:

        feature_key_source = (
            F.concat_ws(
                "||",
                F.col("station_key"),
                F.col("_record_hash"),
            )
        )

    else:

        feature_key_source = (
            F.col("station_key")
        )

    features = features.withColumn(
        "feature_entity_key",
        F.sha2(
            feature_key_source,
            256,
        ),
    )

    if (
        "financial_year_end"
        in features.columns
    ):

        features = (
            features
            .withColumn(
                "feature_period_end",
                F.to_date(
                    F.concat_ws(
                        "-",
                        F.col(
                            "financial_year_end"
                        ).cast("string"),
                        F.lit("03"),
                        F.lit("31"),
                    )
                ),
            )
        )

    for metric in metrics:

        numeric = F.col(
            metric
        ).cast("double")

        features = features.withColumn(
            f"feature__{metric}",
            numeric,
        )

        features = features.withColumn(
            f"feature__log1p__{metric}",
            F.when(
                numeric >= 0,
                F.log1p(numeric),
            ),
        )

        rank_window = Window.orderBy(
            numeric.asc_nulls_last()
        )

        features = features.withColumn(
            f"feature__percent_rank__{metric}",
            F.percent_rank().over(
                rank_window
            ),
        )

        stats = (
            features
            .agg(
                F.avg(numeric).alias(
                    "mean_value"
                ),
                F.stddev_pop(
                    numeric
                ).alias(
                    "std_value"
                ),
            )
            .collect()[0]
        )

        mean_value = stats[
            "mean_value"
        ]

        std_value = stats[
            "std_value"
        ]

        if (
            mean_value is not None
            and std_value is not None
            and std_value != 0
        ):

            zscore = (
                numeric
                - F.lit(
                    float(mean_value)
                )
            ) / F.lit(
                float(std_value)
            )

        else:

            zscore = F.lit(0.0)

        features = features.withColumn(
            f"feature__zscore__{metric}",
            zscore,
        )

    return features


def write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    """Write JSON metadata."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    """Execute the repaired Silver -> Gold pipeline."""

    config = load_config()

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName(
            "RailFlowORRSilverToGoldV2"
        )
        .config(
            "spark.ui.enabled",
            "false",
        )
        .config(
            "spark.sql.shuffle.partitions",
            "4",
        )
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel(
        "ERROR"
    )

    silver_path = (
        PROJECT_ROOT
        / config["silver_path"]
    )

    station_path = (
        PROJECT_ROOT
        / config["station_mart_path"]
    )

    summary_path = (
        PROJECT_ROOT
        / config["summary_mart_path"]
    )

    feature_path = (
        PROJECT_ROOT
        / config["feature_table_path"]
    )

    quality_path = (
        PROJECT_ROOT
        / config["quality_report"]
    )

    contract_path = (
        PROJECT_ROOT
        / config["feature_contract"]
    )

    dictionary_path = (
        PROJECT_ROOT
        / config["data_dictionary"]
    )

    print("=" * 72)
    print("RAILFLOW - SILVER TO GOLD V2")
    print("=" * 72)

    silver = spark.read.parquet(
        str(silver_path)
    )

    silver_rows = silver.count()

    print(
        "Silver rows:",
        silver_rows,
    )

    print()
    print("Original Silver types:")

    for name, dtype in silver.dtypes:
        print(
            f"  {name:<60} {dtype}"
        )

    (
        working,
        metrics,
        metric_profile,
    ) = materialise_business_metrics(
        silver
    )

    if not metrics:

        raise RuntimeError(
            "Metric profiling found no "
            "numeric station-usage fields."
        )

    primary_metric = (
        choose_primary_metric(
            metrics
        )
    )

    dimensions = (
        identify_dimensions(
            working,
            metrics,
        )
    )

    print()
    print(
        "Detected metrics:",
        metrics,
    )

    print(
        "Primary metric:",
        primary_metric,
    )

    print()
    print("Metric profiling:")

    for (
        column,
        profile,
    ) in metric_profile.items():

        print(
            f"  {column}: {profile}"
        )

    station_mart = (
        create_station_mart(
            working,
            dimensions,
            metrics,
            primary_metric,
        )
    )

    summary_mart = (
        create_summary_mart(
            station_mart,
            metrics,
            primary_metric,
        )
    )

    feature_table = (
        create_feature_table(
            station_mart,
            metrics,
        )
    )

    station_rows = (
        station_mart.count()
    )

    feature_rows = (
        feature_table.count()
    )

    null_feature_keys = (
        feature_table
        .filter(
            F.col(
                "feature_entity_key"
            ).isNull()
        )
        .count()
    )

    duplicate_feature_keys = (
        feature_table
        .groupBy(
            "feature_entity_key"
        )
        .count()
        .filter(
            F.col("count") > 1
        )
        .count()
    )

    primary_non_null = (
        station_mart
        .filter(
            F.col(
                primary_metric
            ).isNotNull()
        )
        .count()
    )

    if station_rows != silver_rows:
        raise RuntimeError(
            "Station mart does not "
            "reconcile with Silver."
        )

    if feature_rows != station_rows:
        raise RuntimeError(
            "Feature table row-count "
            "reconciliation failed."
        )

    if null_feature_keys != 0:
        raise RuntimeError(
            "Null feature entity keys found."
        )

    if duplicate_feature_keys != 0:
        raise RuntimeError(
            "Duplicate feature entity keys found."
        )

    if primary_non_null == 0:
        raise RuntimeError(
            "Primary business metric contains "
            "no usable numeric values."
        )

    (
        station_mart.write
        .mode("overwrite")
        .option(
            "compression",
            "snappy",
        )
        .parquet(
            str(station_path)
        )
    )

    (
        summary_mart.write
        .mode("overwrite")
        .option(
            "compression",
            "snappy",
        )
        .parquet(
            str(summary_path)
        )
    )

    (
        feature_table.write
        .mode("overwrite")
        .option(
            "compression",
            "snappy",
        )
        .parquet(
            str(feature_path)
        )
    )

    persisted_station_rows = (
        spark.read
        .parquet(
            str(station_path)
        )
        .count()
    )

    persisted_feature_rows = (
        spark.read
        .parquet(
            str(feature_path)
        )
        .count()
    )

    persisted_summary_rows = (
        spark.read
        .parquet(
            str(summary_path)
        )
        .count()
    )

    quality_checks = {
        "minimum_expected_rows": (
            station_rows >= 2000
        ),
        "station_mart_reconciles": (
            station_rows
            == silver_rows
        ),
        "feature_table_reconciles": (
            feature_rows
            == station_rows
        ),
        "feature_key_complete": (
            null_feature_keys == 0
        ),
        "feature_key_unique": (
            duplicate_feature_keys == 0
        ),
        "metrics_detected": (
            len(metrics) > 0
        ),
        "primary_metric_populated": (
            primary_non_null > 0
        ),
        "station_persistence_reconciles": (
            persisted_station_rows
            == station_rows
        ),
        "feature_persistence_reconciles": (
            persisted_feature_rows
            == feature_rows
        ),
        "summary_mart_created": (
            persisted_summary_rows == 1
        ),
    }

    quality = {
        "dataset_id": config[
            "dataset_id"
        ],
        "layer": "gold",
        "release_period": config[
            "release_period"
        ],
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "silver_row_count": silver_rows,
        "station_mart_row_count": (
            station_rows
        ),
        "feature_table_row_count": (
            feature_rows
        ),
        "summary_mart_row_count": (
            persisted_summary_rows
        ),
        "metric_columns": metrics,
        "metric_profile": (
            metric_profile
        ),
        "dimension_columns": (
            dimensions
        ),
        "primary_usage_metric": (
            primary_metric
        ),
        "primary_metric_non_null_rows": (
            primary_non_null
        ),
        "duplicate_feature_keys": (
            duplicate_feature_keys
        ),
        "null_feature_keys": (
            null_feature_keys
        ),
        "quality_checks": (
            quality_checks
        ),
    }

    write_json(
        quality_path,
        quality,
    )

    contract = {
        "dataset_id": config[
            "dataset_id"
        ],
        "layer": "gold",
        "asset_type": (
            "ml_feature_table"
        ),
        "release_period": config[
            "release_period"
        ],
        "pipeline_version": config[
            "pipeline_version"
        ],
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "primary_entity_key": (
            "feature_entity_key"
        ),
        "entity_key": (
            "station_key"
        ),
        "event_time": (
            "feature_period_end"
        ),
        "source_metrics": metrics,
        "feature_families": [
            "raw_numeric",
            "log1p",
            "percent_rank",
            "zscore",
        ],
        "fields": [
            {
                "name": field.name,
                "type": (
                    field.dataType.simpleString()
                ),
                "nullable": field.nullable,
            }
            for field in (
                feature_table.schema.fields
            )
        ],
    }

    write_json(
        contract_path,
        contract,
    )

    dictionary_lines = [
        "# RailFlow ORR Station Usage - Gold Layer",
        "",
        "## Detected Business Metrics",
        "",
    ]

    for metric in metrics:
        dictionary_lines.append(
            f"- `{metric}`"
        )

    dictionary_lines.extend(
        [
            "",
            "## Primary Usage Metric",
            "",
            f"`{primary_metric}`",
            "",
            "## ML Feature Table",
            "",
            "| Column | Type |",
            "|---|---|",
        ]
    )

    for field in (
        feature_table.schema.fields
    ):

        dictionary_lines.append(
            f"| `{field.name}` | "
            f"`{field.dataType.simpleString()}` |"
        )

    dictionary_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dictionary_path.write_text(
        "\n".join(
            dictionary_lines
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("GOLD STATION MART SAMPLE")
    print("=" * 72)

    station_mart.show(
        5,
        truncate=25,
    )

    print()
    print("=" * 72)
    print("ML FEATURE TABLE SAMPLE")
    print("=" * 72)

    feature_table.show(
        5,
        truncate=25,
    )

    print()
    print(
        "Station mart rows:",
        station_rows,
    )

    print(
        "Feature rows:",
        feature_rows,
    )

    print(
        "Summary rows:",
        persisted_summary_rows,
    )

    print(
        "Metric count:",
        len(metrics),
    )

    print(
        "Primary metric:",
        primary_metric,
    )

    print()
    print("=" * 72)
    print("SILVER -> GOLD PIPELINE: PASS")
    print("=" * 72)

    spark.stop()


if __name__ == "__main__":
    main()
