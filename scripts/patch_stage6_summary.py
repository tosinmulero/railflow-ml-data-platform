"""Patch Stage 6 dbt summary-model generation."""

from pathlib import Path

project_root = Path(__file__).resolve().parents[1]

generator = (
    project_root
    / "scripts"
    / "build_dbt_models.py"
)

text = generator.read_text(
    encoding="utf-8"
)

start_marker = '    summary_sql = """'

end_marker = '''
    write(
        DBT_ROOT
        / "models"
        / "marts"
        / "mart_station_usage_summary.sql",
        summary_sql,
    )
'''

start = text.find(start_marker)

if start == -1:
    raise RuntimeError(
        "Could not locate summary_sql block."
    )

end = text.find(
    end_marker,
    start,
)

if end == -1:
    raise RuntimeError(
        "Could not locate summary-model write block."
    )

replacement = '''    summary_sql = (
        "{{ config(materialized='table') }}\\n\\n"
        "select\\n    "
        + ",\\n    ".join(
            summary_expressions
        )
        + "\\nfrom {{ ref('fct_station_usage') }}\\n"
    )

'''

patched = (
    text[:start]
    + replacement
    + text[end:]
)

generator.write_text(
    patched,
    encoding="utf-8",
)

print(
    "DBT generator summary template patched."
)
