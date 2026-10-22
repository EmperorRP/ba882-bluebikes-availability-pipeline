{{ config(severity='warn') }}
select weather_record_id, weather_at_utc, forecast_metadata_quality
from {{ ref('stg_weather') }}
where source_type = 'forecast_api' and forecast_metadata_quality != 'valid'
