select 'trip' as feed, ride_id as identifier
from {{ ref('stg_trips') }}
where duration_seconds < 0
    or start_latitude not between -90 and 90 or end_latitude not between -90 and 90
    or start_longitude not between -180 and 180 or end_longitude not between -180 and 180
union all
select 'weather', weather_record_id
from {{ ref('stg_weather') }}
where humidity_pct not between 0 and 100 or precipitation_mm < 0 or wind_speed_kmh < 0
    or timestamp_trunc(weather_at_utc, hour) != weather_at_utc
