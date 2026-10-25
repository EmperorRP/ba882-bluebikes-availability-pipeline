{{ config(materialized='view', schema='ml', tags=['point_in_time_ml']) }}
-- Explicit allowlist: feature columns + target and evaluation keys only. No future label provenance as predictors.
select f.prediction_id,f.station_id,f.prediction_at_utc,f.target_at_utc,f.horizon_minutes,
    f.target_local_hour,f.target_local_day_of_week,f.target_is_weekend,
    f.origin_bikes_available,f.origin_docks_available,f.origin_capacity,f.origin_bike_fill_ratio,f.origin_report_age_seconds,
    f.bikes_available_lag,f.has_lag_inventory,
    f.observed_departures_matching_hour_lookback,f.observed_arrivals_matching_hour_lookback,
    f.trip_history_observed_dates,f.has_trip_history,
    f.forecast_temperature_c,f.forecast_humidity_pct,f.forecast_precipitation_mm,f.forecast_wind_speed_kmh,f.has_forecast_weather,
    l.target_has_bike
from {{ ref('mart_station_availability_features') }} f
join {{ ref('mart_station_availability_labels') }} l using(prediction_id)
where f.is_origin_usable and l.target_has_bike is not null
