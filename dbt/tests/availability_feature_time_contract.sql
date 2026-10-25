{{ config(tags=['point_in_time_ml']) }}
select prediction_id from {{ ref('mart_station_availability_features') }}
where target_at_utc != timestamp_add(prediction_at_utc,interval horizon_minutes minute)
   or origin_available_at_utc>prediction_at_utc or origin_metadata_available_at_utc>prediction_at_utc
   or (is_origin_usable and origin_reported_at_utc>prediction_at_utc)
   or lag_available_at_utc>timestamp_sub(prediction_at_utc,interval lag_minutes minute)
   or trip_history_available_at_utc>prediction_at_utc
   or timestamp_add(trip_history_latest_event_hour_utc,interval 1 hour)>prediction_at_utc
   or weather_available_at_utc>prediction_at_utc or weather_fetched_at_utc>prediction_at_utc
   or (has_forecast_weather and (weather_at_utc != target_hour_utc or weather_at_utc<=prediction_at_utc))
   or (has_lag_inventory and (bikes_available_lag is null or lag_reported_at_utc>timestamp_sub(prediction_at_utc,interval lag_minutes minute)
       or timestamp_diff(timestamp_sub(prediction_at_utc,interval lag_minutes minute),lag_reported_at_utc,second)>{{ var('availability_max_report_age_minutes') }}*60))
   or (not has_lag_inventory and bikes_available_lag is not null)
   or (not is_origin_usable and (origin_bikes_available is not null or origin_docks_available is not null or origin_capacity is not null or origin_bike_fill_ratio is not null))
   or (not has_trip_history and (observed_departures_matching_hour_lookback is not null or observed_arrivals_matching_hour_lookback is not null))
   or (not has_forecast_weather and (forecast_temperature_c is not null or forecast_precipitation_mm is not null))
