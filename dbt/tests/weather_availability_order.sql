-- Forecasts fetched after their valid time are retained, but cannot be future candidates.
select weather_record_id
from {{ ref('stg_weather') }}
where available_at_utc < ingested_at_utc
    or (source_type = 'forecast_api' and available_at_utc < forecast_fetched_at_utc)
    or (is_future_at_available_time and (
        source_type != 'forecast_api' or forecast_metadata_quality != 'valid'
        or available_at_utc is null or forecast_fetched_at_utc is null
        or weather_at_utc < available_at_utc
    ))
