# RailFlow ORR Station Usage — Silver Data Dictionary

## Dataset

Cleaned and strongly typed station-usage dataset derived from the Office of Rail and Road Bronze layer.

## Station identity fields

- No explicit station identifier was detected; `_record_hash` is used as the deterministic key source.

## Columns

| Column | Spark type | Nullable |
|---|---|---|
| `table_1410_passenger_entries_exits_and_interchanges_by_station_great_britain_annual_data_april_2024_to_march_2025` | `string` | True |
| `c1` | `string` | True |
| `c2` | `string` | True |
| `c3` | `string` | True |
| `c4` | `string` | True |
| `c5` | `string` | True |
| `c6` | `string` | True |
| `c7` | `string` | True |
| `c8` | `string` | True |
| `c9` | `string` | True |
| `c10` | `string` | True |
| `c11` | `string` | True |
| `c12` | `string` | True |
| `c13` | `string` | True |
| `c14` | `string` | True |
| `c15` | `string` | True |
| `c16` | `string` | True |
| `c17` | `string` | True |
| `_record_hash` | `string` | True |
| `_source_system` | `string` | True |
| `_source_dataset` | `string` | True |
| `_source_release` | `string` | True |
| `_ingestion_run_id` | `string` | True |
| `_ingested_at_utc` | `timestamp` | True |
| `_source_file` | `string` | True |
| `station_key` | `string` | True |
| `financial_year_start` | `int` | False |
| `financial_year_end` | `int` | False |
| `_silver_pipeline_version` | `string` | False |
| `_silver_processed_at_utc` | `timestamp` | False |
