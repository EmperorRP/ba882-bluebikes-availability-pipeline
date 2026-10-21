select 'trip_missing' as discrepancy, ride_id as identifier
from (
    select nullif(trim(ride_id), '') as ride_id from {{ source('bluebikes', 'historical_trips') }}
    except distinct
    select ride_id from {{ ref('stg_trips') }}
)
union all
select 'trip_unexpected', ride_id
from (
    select ride_id from {{ ref('stg_trips') }}
    except distinct
    select nullif(trim(ride_id), '') from {{ source('bluebikes', 'historical_trips') }}
)
union all
select 'weather_missing', to_json_string(x)
from (
    select weather_time as weather_at_utc, lower(trim(source)) as source_type,
           forecast_issued_at as forecast_fetched_at_utc
    from {{ source('weather', 'weather_hourly') }}
    except distinct
    select weather_at_utc, source_type, forecast_fetched_at_utc from {{ ref('stg_weather') }}
) x
union all
select 'weather_unexpected', to_json_string(x)
from (
    select weather_at_utc, source_type, forecast_fetched_at_utc from {{ ref('stg_weather') }}
    except distinct
    select weather_time, lower(trim(source)), forecast_issued_at
    from {{ source('weather', 'weather_hourly') }}
) x
