{{ config(materialized='view', tags=['trip_weather_staging']) }}

with normalized as (
    select
        weather_time as weather_at_utc,
        lower(trim(source)) as source_type,
        temperature_c, humidity_pct, precipitation_mm, wind_speed_kmh,
        forecast_issued_at as forecast_fetched_at_utc,
        ingested_at as ingested_at_utc
    from {{ source('weather', 'weather_hourly') }}
    qualify row_number() over (
        partition by weather_time, source, forecast_issued_at
        order by ingested_at desc, temperature_c desc, humidity_pct desc,
                 precipitation_mm desc, wind_speed_kmh desc
    ) = 1
), availability as (
    select *,
        case
            when source_type = 'historical' then ingested_at_utc
            when forecast_fetched_at_utc is not null and ingested_at_utc is not null
                then greatest(forecast_fetched_at_utc, ingested_at_utc)
        end as available_at_utc,
        case
            when source_type = 'historical' then 'not_applicable'
            when forecast_fetched_at_utc is null then 'missing_fetch_time'
            when ingested_at_utc is null then 'missing_ingestion_time'
            when forecast_fetched_at_utc > ingested_at_utc then 'fetch_after_ingestion'
            else 'valid'
        end as forecast_metadata_quality
    from normalized
)
select *,
    to_hex(sha256(to_json_string(struct(
        weather_at_utc as weather_time, source_type as source,
        forecast_fetched_at_utc as forecast_fetched_at
    )))) as weather_record_id,
    datetime(weather_at_utc, 'America/New_York') as weather_at_local,
    case
        when source_type = 'historical' then 'historical_reanalysis'
        when forecast_metadata_quality != 'valid' then 'unversioned_forecast'
        when weather_at_utc < available_at_utc then 'past_or_current_at_fetch'
        else 'future_at_fetch'
    end as weather_temporal_role,
    coalesce(source_type = 'forecast_api' and forecast_metadata_quality = 'valid'
        and weather_at_utc >= available_at_utc, false) as is_future_at_available_time,
    case when source_type = 'forecast_api' and forecast_metadata_quality = 'valid'
        then timestamp_diff(weather_at_utc, forecast_fetched_at_utc, second) / 3600.0
    end as lead_hours_at_fetch
from availability
