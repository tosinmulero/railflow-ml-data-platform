select
    *
from {{ ref('fct_station_usage') }}
where primary_usage_value < 0
