"""
RailFlow Bronze → Silver pipeline.

Transforms ORR station-usage Bronze data into a strongly typed,
validated and deduplicated Silver dataset.

Engineering controls:
- null-value standardisation
- string cleaning
- numeric type inference
- deterministic business keys
- exact-record deduplication
- schema capture
- data contract generation
- data-quality gates
- row-count reconciliation
- Snappy Parquet storage
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    FloatType,
    IntegerType,
    LongType,
    ShortType,
    StringType,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "silver_station_usage.json"
)


NULL_TOKENS = {
    "",
    "na",
    "n/a",
    "null",
    "none",
    "..",
    ":",
}


NUMERIC_HINTS = {
    "entry",
    "entries",
    "exit",
    "exits",
    "interchange",
    "interchanges",
    "passenger",
    "passengers",
    "usage",
    "journey",
    "journeys",
    "total",
    "easting",
    "northing",
    "latitude",
    "longitude",
}


IDENTIFIER_HINTS = {
    "station",
    "station_name",
    "station_code",
    "crs",
    "nlc",
}


def load_config() -> dict[str, Any]:
    """Load Silver pipeline configuration."""

    return json.loads(
        CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )


def normalise_strings(df: DataFrame) -> DataFrame:
    """Trim strings and standardise missing-value tokens."""

    for field in df.schema.fields:

        if isinstance(field.dataType, StringType):

            column = field.name

            cleaned = F.trim(
                F.col(column)
            )

            df = df.withColumn(
                column,
                F.when(
                    F.lower(cleaned).isin(
                        sorted(NULL_TOKENS)
                    ),
                    F.lit(None),
                ).otherwise(cleaned),
            )

    return df


def has_numeric_hint(column: str) -> bool:
    """Return True when a column name appears numeric by semantics."""

    tokens = set(
        re.split(
            r"[_\W]+",
            column.lower(),
        )
    )

    if "code" in tokens:
        return False

    return bool(
        tokens.intersection(
            NUMERIC_HINTS
        )
    )


def cast_existing_numeric_columns(
    df: DataFrame,
) -> DataFrame:
    """Standardise Spark integral/floating types."""

    for field in df.schema.fields:

        column = field.name

        if isinstance(
            field.dataType,
            (
                IntegerType,
                ShortType,
            ),
        ):
            df = df.withColumn(
                column,
                F.col(column).cast(
                    LongType()
                ),
            )

        elif isinstance(
            field.dataType,
            FloatType,
        ):
            df = df.withColumn(
                column,
                F.col(column).cast(
                    DoubleType()
                ),
            )

    return df


def cast_numeric_strings(
    df: DataFrame,
) -> tuple[DataFrame, list[str]]:
    """
    Convert semantically numeric string columns when at least
    95% of populated values parse successfully.
    """

    converted: list[str] = []

    string_fields = [
        field
        for field in df.schema.fields
        if isinstance(
            field.dataType,
            StringType,
        )
    ]

    for field in string_fields:

        column = field.name

        if not has_numeric_hint(column):
            continue

        normalised = F.regexp_replace(
            F.col(column),
            ",",
            "",
        )

        populated = df.filter(
            F.col(column).isNotNull()
        ).count()

        if populated == 0:
            continue

        parseable = df.filter(
            F.col(column).isNotNull()
            & normalised.rlike(
                r"^-?[0-9]+(?:\.[0-9]+)?$"
            )
        ).count()

        parse_ratio = (
            parseable
            / populated
        )

        if parse_ratio < 0.95:
            continue

        decimal_values = df.filter(
            F.col(column).isNotNull()
            & normalised.contains(".")
        ).count()

        target_type = (
            DoubleType()
            if decimal_values > 0
            else LongType()
        )

        df = df.withColumn(
            column,
            F.when(
                normalised.rlike(
                    r"^-?[0-9]+(?:\.[0-9]+)?$"
                ),
                normalised.cast(
                    target_type
                ),
            ).otherwise(
                F.lit(None)
            ),
        )

        converted.append(column)

    return df, converted


def find_identity_columns(
    df: DataFrame,
) -> list[str]:
    """Identify likely station identity fields."""

    candidates: list[str] = []

    for column in df.columns:

        lower = column.lower()

        if column.startswith("_"):
            continue

        if (
            lower in IDENTIFIER_HINTS
            or (
                "station" in lower
                and (
                    "name" in lower
                    or "code" in lower
                )
            )
        ):
            candidates.append(column)

    return candidates[:4]


def build_station_key(
    df: DataFrame,
    identity_columns: list[str],
) -> DataFrame:
    """Create deterministic Silver station key."""

    if identity_columns:

        key_values = [
            F.coalesce(
                F.lower(
                    F.trim(
                        F.col(column).cast(
                            "string"
                        )
                    )
                ),
                F.lit(""),
            )
            for column in identity_columns
        ]

        expression = F.concat_ws(
            "||",
            *key_values,
        )

    else:

        expression = F.col(
            "_record_hash"
        )

    return df.withColumn(
        "station_key",
        F.sha2(
            expression,
            256,
        ),
    )


def create_contract(
    df: DataFrame,
    config: dict[str, Any],
    identity_columns: list[str],
    converted_columns: list[str],
) -> dict[str, Any]:
    """Build a machine-readable technical data contract."""

    fields = []

    for field in df.schema.fields:

        fields.append(
            {
                "name": field.name,
                "type": field.dataType.simpleString(),
                "nullable": field.nullable,
            }
        )

    return {
        "dataset_id": config["dataset_id"],
        "layer": "silver",
        "release_period": config[
            "release_period"
        ],
        "pipeline_version": config[
            "pipeline_version"
        ],
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "primary_surrogate_key": (
            "station_key"
        ),
        "record_lineage_key": (
            "_record_hash"
        ),
        "station_identity_columns": (
            identity_columns
        ),
        "automatically_cast_columns": (
            converted_columns
        ),
        "fields": fields,
    }


def create_data_dictionary(
    df: DataFrame,
    path: Path,
    identity_columns: list[str],
) -> None:
    """Generate a recruiter-readable Markdown data dictionary."""

    rows = [
        "# RailFlow ORR Station Usage — Silver Data Dictionary",
        "",
        "## Dataset",
        "",
        "Cleaned and strongly typed station-usage dataset "
        "derived from the Office of Rail and Road Bronze layer.",
        "",
        "## Station identity fields",
        "",
    ]

    if identity_columns:

        for column in identity_columns:
            rows.append(
                f"- `{column}`"
            )

    else:
        rows.append(
            "- No explicit station identifier was detected; "
            "`_record_hash` is used as the deterministic key source."
        )

    rows.extend(
        [
            "",
            "## Columns",
            "",
            "| Column | Spark type | Nullable |",
            "|---|---|---|",
        ]
    )

    for field in df.schema.fields:

        rows.append(
            f"| `{field.name}` | "
            f"`{field.dataType.simpleString()}` | "
            f"{field.nullable} |"
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Execute Bronze → Silver."""

    config = load_config()

    bronze_path = (
        PROJECT_ROOT
        / config["bronze_path"]
    )

    silver_path = (
        PROJECT_ROOT
        / config["silver_path"]
    )

    quality_path = (
        PROJECT_ROOT
        / config["quality_report"]
    )

    schema_path = (
        PROJECT_ROOT
        / config["schema_file"]
    )

    contract_path = (
        PROJECT_ROOT
        / config["data_contract"]
    )

    dictionary_path = (
        PROJECT_ROOT
        / config["data_dictionary"]
    )

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName(
            "RailFlowORRBronzeToSilver"
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

    print("=" * 72)
    print("RAILFLOW — BRONZE → SILVER")
    print("=" * 72)

    bronze = spark.read.parquet(
        str(bronze_path)
    )

    bronze_rows = bronze.count()

    print(
        "Bronze rows    :",
        bronze_rows,
    )

    print(
        "Bronze columns :",
        len(bronze.columns),
    )

    df = normalise_strings(
        bronze
    )

    df = cast_existing_numeric_columns(
        df
    )

    df, converted_columns = (
        cast_numeric_strings(df)
    )

    identity_columns = (
        find_identity_columns(df)
    )

    df = build_station_key(
        df,
        identity_columns,
    )

    df = (
        df
        .withColumn(
            "financial_year_start",
            F.lit(
                config[
                    "financial_year_start"
                ]
            ).cast("int"),
        )
        .withColumn(
            "financial_year_end",
            F.lit(
                config[
                    "financial_year_end"
                ]
            ).cast("int"),
        )
        .withColumn(
            "_silver_pipeline_version",
            F.lit(
                config[
                    "pipeline_version"
                ]
            ),
        )
        .withColumn(
            "_silver_processed_at_utc",
            F.current_timestamp(),
        )
    )

    before_dedup = df.count()

    df = df.dropDuplicates(
        ["_record_hash"]
    )

    silver_rows = df.count()

    duplicates_removed = (
        before_dedup
        - silver_rows
    )

    duplicate_hashes = (
        df.groupBy(
            "_record_hash"
        )
        .count()
        .filter(
            F.col("count") > 1
        )
        .count()
    )

    null_station_keys = (
        df.filter(
            F.col(
                "station_key"
            ).isNull()
        )
        .count()
    )

    if silver_rows == 0:
        raise RuntimeError(
            "Silver quality gate failed: "
            "dataset is empty."
        )

    if silver_rows > bronze_rows:
        raise RuntimeError(
            "Silver quality gate failed: "
            "Silver row count exceeds Bronze."
        )

    if duplicate_hashes != 0:
        raise RuntimeError(
            "Silver quality gate failed: "
            "duplicate record hashes remain."
        )

    if null_station_keys != 0:
        raise RuntimeError(
            "Silver quality gate failed: "
            "station_key contains null values."
        )

    print()
    print(
        "Station identity columns:",
        identity_columns,
    )

    print(
        "Auto-cast numeric columns:",
        converted_columns,
    )

    print(
        "Duplicates removed:",
        duplicates_removed,
    )

    (
        df.write
        .mode("overwrite")
        .option(
            "compression",
            "snappy",
        )
        .parquet(
            str(silver_path)
        )
    )

    persisted = spark.read.parquet(
        str(silver_path)
    )

    persisted_rows = (
        persisted.count()
    )

    if persisted_rows != silver_rows:
        raise RuntimeError(
            "Silver reconciliation failed: "
            f"memory={silver_rows}, "
            f"persisted={persisted_rows}"
        )

    quality_report = {
        "dataset_id": config[
            "dataset_id"
        ],
        "layer": "silver",
        "release_period": config[
            "release_period"
        ],
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "bronze_row_count": bronze_rows,
        "rows_before_deduplication": (
            before_dedup
        ),
        "silver_row_count": (
            silver_rows
        ),
        "duplicates_removed": (
            duplicates_removed
        ),
        "duplicate_record_hashes": (
            duplicate_hashes
        ),
        "null_station_keys": (
            null_station_keys
        ),
        "column_count": len(
            df.columns
        ),
        "station_identity_columns": (
            identity_columns
        ),
        "automatically_cast_columns": (
            converted_columns
        ),
        "quality_checks": {
            "dataset_not_empty": (
                silver_rows > 0
            ),
            "minimum_expected_rows": (
                silver_rows >= 2000
            ),
            "row_count_not_increased": (
                silver_rows
                <= bronze_rows
            ),
            "record_hash_unique": (
                duplicate_hashes == 0
            ),
            "station_key_complete": (
                null_station_keys == 0
            ),
            "persisted_row_reconciliation": (
                persisted_rows
                == silver_rows
            ),
        },
    }

    quality_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    quality_path.write_text(
        json.dumps(
            quality_report,
            indent=2,
        ),
        encoding="utf-8",
    )

    schema_path.write_text(
        json.dumps(
            df.schema.jsonValue(),
            indent=2,
        ),
        encoding="utf-8",
    )

    contract = create_contract(
        df,
        config,
        identity_columns,
        converted_columns,
    )

    contract_path.write_text(
        json.dumps(
            contract,
            indent=2,
        ),
        encoding="utf-8",
    )

    create_data_dictionary(
        df,
        dictionary_path,
        identity_columns,
    )

    print()
    print("=" * 72)
    print("SILVER DATA SAMPLE")
    print("=" * 72)

    persisted.show(
        5,
        truncate=30,
    )

    print()
    print(
        "Silver rows       :",
        persisted_rows,
    )

    print(
        "Silver columns    :",
        len(persisted.columns),
    )

    print(
        "Duplicates removed:",
        duplicates_removed,
    )

    print(
        "Null station keys :",
        null_station_keys,
    )

    print(
        "Quality report    :",
        quality_path,
    )

    print(
        "Data contract     :",
        contract_path,
    )

    print(
        "Data dictionary   :",
        dictionary_path,
    )

    print()
    print("=" * 72)
    print("BRONZE → SILVER PIPELINE: PASS")
    print("=" * 72)

    spark.stop()


if __name__ == "__main__":
    main()
