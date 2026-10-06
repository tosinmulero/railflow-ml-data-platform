"""
Generate RailFlow dbt models from the actual Gold-layer metadata.

This prevents the dbt project from relying on hard-coded ORR metric
column names and keeps SQL aligned with the Spark Gold contract.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DBT_ROOT = PROJECT_ROOT / "dbt"

GOLD_REPORT = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "orr"
    / "station_usage"
    / "gold_quality_report.json"
)


def quote_identifier(value: str) -> str:
    """DuckDB-safe quoted identifier."""

    return '"' + value.replace('"', '""') + '"'


def write(path: Path, text: str) -> None:
    """Write UTF-8 text."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        text.strip() + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Generate dbt SQL and YAML assets."""

    report = json.loads(
        GOLD_REPORT.read_text(
            encoding="utf-8"
        )
    )

    metrics = report[
        "metric_columns"
    ]

    dimensions = report.get(
        "dimension_columns",
        [],
    )

    primary_metric = report[
        "primary_usage_metric"
    ]

    if not metrics:
        raise RuntimeError(
            "Gold metadata contains no business metrics."
        )

    quoted_primary = quote_identifier(
        primary_metric
    )

    # -------------------------------------------------------------
    # Staging: station mart
    # -------------------------------------------------------------

    write(
        DBT_ROOT
        / "models"
        / "staging"
        / "stg_station_usage.sql",
        """
{{ config(materialized='view') }}

select
    *
{% set station_path = (
    env_var("RAILFLOW_PROJECT_ROOT")
    ~ "/data/gold/orr/station_usage/"
    ~ "station_mart/release=2024_25/*.parquet"
) %}

from read_parquet(
    '{{ station_path }}'
)
""",
    )

    # -------------------------------------------------------------
    # Staging: ML features
    # -------------------------------------------------------------

    write(
        DBT_ROOT
        / "models"
        / "staging"
        / "stg_ml_station_features.sql",
        """
{{ config(materialized='view') }}

select
    *
{% set feature_path = (
    env_var("RAILFLOW_PROJECT_ROOT")
    ~ "/data/gold/orr/station_usage/"
    ~ "ml_features/release=2024_25/*.parquet"
) %}

from read_parquet(
    '{{ feature_path }}'
)
""",
    )

    # -------------------------------------------------------------
    # Intermediate model
    # -------------------------------------------------------------

    metric_completeness = " +\n        ".join(
        (
            f"case when {quote_identifier(metric)} "
            "is not null then 1 else 0 end"
        )
        for metric in metrics
    )

    metric_count = len(metrics)

    interchange_metrics = [
        metric
        for metric in metrics
        if "interchange" in metric.lower()
    ]

    if interchange_metrics:

        interchange_expression = " + ".join(
            (
                f"coalesce("
                f"{quote_identifier(metric)}, 0)"
            )
            for metric in interchange_metrics
        )

        interchange_sql = f"""
    case
        when ({interchange_expression}) > 0
            then true
        else false
    end as has_interchange_activity,
"""

    else:

        interchange_sql = """
    cast(false as boolean) as has_interchange_activity,
"""

    intermediate_sql = f"""
{{{{ config(materialized='view') }}}}

with source as (

    select
        *
    from {{{{ ref('stg_station_usage') }}}}

),

enriched as (

    select
        *,

        case
            when station_usage_percent_rank <= 0.01
                then 'Top 1%'
            when station_usage_percent_rank <= 0.10
                then 'Top 10%'
            when station_usage_percent_rank <= 0.25
                then 'Top Quartile'
            when station_usage_percent_rank <= 0.50
                then 'Upper Half'
            else 'Lower Half'
        end as station_usage_band,

        ln(
            1 + greatest(
                coalesce(
                    cast({quoted_primary} as double),
                    0
                ),
                0
            )
        ) as primary_usage_log1p,

{interchange_sql}

        (
            {metric_completeness}
        )::double / {metric_count} as metric_completeness_ratio

    from source

)

select
    *
from enriched
"""

    write(
        DBT_ROOT
        / "models"
        / "intermediate"
        / "int_station_usage_enriched.sql",
        intermediate_sql,
    )

    # -------------------------------------------------------------
    # Dimension
    # -------------------------------------------------------------

    dimensional_columns = []

    for dimension in dimensions:

        if dimension in (
            "primary_usage_metric",
        ):
            continue

        dimensional_columns.append(
            quote_identifier(dimension)
        )

    dimension_select = ""

    if dimensional_columns:

        dimension_select = (
            ",\n        "
            + ",\n        ".join(
                dimensional_columns
            )
        )

    dim_sql = f"""
{{{{ config(materialized='table') }}}}

select distinct
    station_key
    {dimension_select}
from {{{{ ref('int_station_usage_enriched') }}}}
"""

    write(
        DBT_ROOT
        / "models"
        / "marts"
        / "dim_station.sql",
        dim_sql,
    )

    # -------------------------------------------------------------
    # Fact table
    # -------------------------------------------------------------

    fact_columns = [
        "station_key",
        "_record_hash",
        "financial_year_start",
        "financial_year_end",
    ]

    fact_columns.extend(
        metrics
    )

    fact_columns.extend(
        [
            "primary_usage_metric",
            "primary_usage_value",
            "station_usage_rank",
            "station_usage_percent_rank",
            "station_usage_band",
            "primary_usage_log1p",
            "has_interchange_activity",
            "metric_completeness_ratio",
        ]
    )

    fact_select = ",\n    ".join(
        quote_identifier(column)
        for column in fact_columns
    )

    fact_sql = f"""
{{{{ config(materialized='table') }}}}

select
    {fact_select}
from {{{{ ref('int_station_usage_enriched') }}}}
"""

    write(
        DBT_ROOT
        / "models"
        / "marts"
        / "fct_station_usage.sql",
        fact_sql,
    )

    # -------------------------------------------------------------
    # Executive summary mart
    # -------------------------------------------------------------

    summary_expressions = [
        "count(*) as station_record_count",
        (
            "count(distinct station_key) "
            "as distinct_station_count"
        ),
        (
            "avg(primary_usage_value) "
            "as average_primary_usage"
        ),
        (
            "median(primary_usage_value) "
            "as median_primary_usage"
        ),
        (
            "max(primary_usage_value) "
            "as maximum_primary_usage"
        ),
        (
            "min(primary_usage_value) "
            "as minimum_primary_usage"
        ),
    ]

    for metric in metrics:

        quoted = quote_identifier(
            metric
        )

        summary_expressions.extend(
            [
                (
                    f"sum({quoted}) "
                    f"as {quote_identifier('total__' + metric)}"
                ),
                (
                    f"avg({quoted}) "
                    f"as {quote_identifier('average__' + metric)}"
                ),
            ]
        )

    summary_sql = (
        "{{ config(materialized='table') }}\n\n"
        "select\n    "
        + ",\n    ".join(
            summary_expressions
        )
        + "\nfrom {{ ref('fct_station_usage') }}\n"
    )


    write(
        DBT_ROOT
        / "models"
        / "marts"
        / "mart_station_usage_summary.sql",
        summary_sql,
    )

    # -------------------------------------------------------------
    # ML feature table
    # -------------------------------------------------------------

    write(
        DBT_ROOT
        / "models"
        / "marts"
        / "ml_station_features.sql",
        """
{{ config(materialized='table') }}

select
    *
from {{ ref('stg_ml_station_features') }}
""",
    )

    # -------------------------------------------------------------
    # dbt schema + tests
    # -------------------------------------------------------------

    schema_yml = """
version: 2

models:

  - name: stg_station_usage
    description: >
      dbt staging view over the Spark-generated ORR Gold station
      analytics Parquet dataset.

    columns:

      - name: station_key
        description: Deterministic station entity key.
        data_tests:
          - not_null

      - name: _record_hash
        description: Bronze/Silver source-lineage record hash.
        data_tests:
          - not_null
          - unique

  - name: int_station_usage_enriched
    description: >
      Enriched station usage model containing classification,
      completeness and analytics-ready derived attributes.

    columns:

      - name: station_key
        data_tests:
          - not_null

      - name: station_usage_band
        data_tests:
          - not_null
          - accepted_values:
              arguments:
                values:
                  - "Top 1%"
                  - "Top 10%"
                  - "Top Quartile"
                  - "Upper Half"
                  - "Lower Half"

      - name: metric_completeness_ratio
        data_tests:
          - not_null

  - name: dim_station
    description: >
      Station dimension containing one row per RailFlow station entity.

    columns:

      - name: station_key
        data_tests:
          - not_null
          - unique

  - name: fct_station_usage
    description: >
      Station-level annual ORR usage fact table for analytics
      and downstream reporting.

    columns:

      - name: station_key
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_station')
                field: station_key

      - name: _record_hash
        data_tests:
          - not_null
          - unique

      - name: primary_usage_value
        description: >
          Numeric value of the automatically selected primary
          station usage metric.

  - name: mart_station_usage_summary
    description: >
      Executive-level aggregate station-usage metrics.

  - name: stg_ml_station_features
    description: >
      Staging view over the Spark Gold machine-learning
      feature table.

    columns:

      - name: feature_entity_key
        data_tests:
          - not_null
          - unique

      - name: station_key
        data_tests:
          - not_null

  - name: ml_station_features
    description: >
      Materialised reusable ML feature table for future model
      training and inference pipelines.

    columns:

      - name: feature_entity_key
        data_tests:
          - not_null
          - unique

      - name: station_key
        data_tests:
          - not_null
"""

    write(
        DBT_ROOT
        / "models"
        / "schema.yml",
        schema_yml,
    )

    # -------------------------------------------------------------
    # Singular data-quality tests
    # -------------------------------------------------------------

    write(
        DBT_ROOT
        / "tests"
        / "assert_primary_usage_non_negative.sql",
        """
select
    *
from {{ ref('fct_station_usage') }}
where primary_usage_value < 0
""",
    )

    write(
        DBT_ROOT
        / "tests"
        / "assert_fact_reconciles_to_staging.sql",
        """
with staging as (

    select count(*) as row_count
    from {{ ref('stg_station_usage') }}

),

fact as (

    select count(*) as row_count
    from {{ ref('fct_station_usage') }}

)

select
    staging.row_count as staging_rows,
    fact.row_count as fact_rows
from staging
cross join fact
where staging.row_count <> fact.row_count
""",
    )

    write(
        DBT_ROOT
        / "tests"
        / "assert_feature_reconciles_to_gold.sql",
        """
with staging as (

    select count(*) as row_count
    from {{ ref('stg_ml_station_features') }}

),

final as (

    select count(*) as row_count
    from {{ ref('ml_station_features') }}

)

select
    staging.row_count as staging_rows,
    final.row_count as final_rows
from staging
cross join final
where staging.row_count <> final.row_count
""",
    )

    # -------------------------------------------------------------
    # Exposures
    # -------------------------------------------------------------

    exposures_yml = """
version: 2

exposures:

  - name: railflow_analytics
    label: RailFlow Analytics Layer
    type: dashboard
    maturity: high
    description: >
      Recruiter-facing and business-facing analytics surface
      powered by RailFlow dbt marts.

    depends_on:
      - ref('fct_station_usage')
      - ref('dim_station')
      - ref('mart_station_usage_summary')

    owner:
      name: RailFlow Data Engineering
      email: railflow@example.com

  - name: railflow_ml_feature_consumer
    label: RailFlow ML Feature Consumer
    type: application
    maturity: high
    description: >
      Downstream machine-learning workloads consuming the
      dbt materialised feature table.

    depends_on:
      - ref('ml_station_features')

    owner:
      name: RailFlow ML Engineering
      email: railflow@example.com
"""

    write(
        DBT_ROOT
        / "models"
        / "exposures.yml",
        exposures_yml,
    )

    print("=" * 72)
    print("RAILFLOW DBT MODEL GENERATION")
    print("=" * 72)

    print(
        "Metrics:",
        metrics,
    )

    print(
        "Primary metric:",
        primary_metric,
    )

    print(
        "Dimensions:",
        dimensions,
    )

    print()
    print("DBT MODEL GENERATION: PASS")


if __name__ == "__main__":
    main()
