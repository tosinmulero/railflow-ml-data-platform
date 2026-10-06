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
