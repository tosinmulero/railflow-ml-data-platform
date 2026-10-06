"""Validate Stage 6 dbt materialisations."""

from pathlib import Path

import duckdb

project_root = Path(__file__).resolve().parents[1]

database = (
    project_root
    / "dbt"
    / "railflow_analytics.duckdb"
)

assert database.exists()

connection = duckdb.connect(
    str(database),
    read_only=True,
)

relations = connection.execute(
    """
    select
        table_schema,
        table_name,
        table_type
    from information_schema.tables
    where table_schema in (
        'staging',
        'intermediate',
        'marts'
    )
    order by
        table_schema,
        table_name
    """
).fetchall()

print("=" * 72)
print("RAILFLOW DBT MATERIALISATIONS")
print("=" * 72)

for relation in relations:
    print(relation)

required = {
    (
        "staging",
        "stg_station_usage",
    ),
    (
        "staging",
        "stg_ml_station_features",
    ),
    (
        "intermediate",
        "int_station_usage_enriched",
    ),
    (
        "marts",
        "dim_station",
    ),
    (
        "marts",
        "fct_station_usage",
    ),
    (
        "marts",
        "mart_station_usage_summary",
    ),
    (
        "marts",
        "ml_station_features",
    ),
}

available = {
    (schema, table)
    for schema, table, _ in relations
}

missing = required - available

assert not missing, (
    f"Missing relations: {missing}"
)

fact_rows = connection.execute(
    """
    select count(*)
    from marts.fct_station_usage
    """
).fetchone()[0]

feature_rows = connection.execute(
    """
    select count(*)
    from marts.ml_station_features
    """
).fetchone()[0]

summary_rows = connection.execute(
    """
    select count(*)
    from marts.mart_station_usage_summary
    """
).fetchone()[0]

dimension_rows = connection.execute(
    """
    select count(*)
    from marts.dim_station
    """
).fetchone()[0]

print()
print(
    "Fact rows      :",
    fact_rows,
)

print(
    "Dimension rows :",
    dimension_rows,
)

print(
    "Feature rows   :",
    feature_rows,
)

print(
    "Summary rows   :",
    summary_rows,
)

assert fact_rows >= 2000
assert dimension_rows >= 2000
assert feature_rows >= 2000
assert summary_rows == 1

print()
print(
    "DBT MATERIALISATION: PASS"
)

connection.close()
