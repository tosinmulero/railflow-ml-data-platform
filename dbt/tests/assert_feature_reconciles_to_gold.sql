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
