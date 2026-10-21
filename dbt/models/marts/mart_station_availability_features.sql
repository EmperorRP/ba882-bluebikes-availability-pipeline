{{ config(materialized='table', schema='marts', tags=['point_in_time_ml'],
    partition_by={'field':'prediction_at_utc','data_type':'timestamp','granularity':'day'},
    cluster_by=['station_id','horizon_minutes']) }}
-- Origins are actual warehouse collection times; optional missing features remain NULL.
with requests as (select * from {{ ref('int_availability_prediction_requests') }}),
lagged as (
    select p.prediction_id, h.inventory_observation_id as lag_observation_id,
        h.source_available_at_utc as lag_available_at_utc,
        h.reported_at_utc as lag_reported_at_utc,
        coalesce(h.is_bike_observation_usable and timestamp_diff(
            timestamp_sub(p.prediction_at_utc,interval {{ var('availability_lag_minutes') }} minute),h.reported_at_utc,second
        ) between 0 and {{ var('availability_max_report_age_minutes') }}*60,false) as has_lag_inventory,
        h.bikes_available as lag_bikes
    from requests p left join {{ ref('fct_station_inventory_history') }} h
      on p.station_id=h.station_id
      and h.source_available_at_utc<=timestamp_sub(p.prediction_at_utc,interval {{ var('availability_lag_minutes') }} minute)
    qualify row_number() over(partition by p.prediction_id order by h.source_available_at_utc desc,h.inventory_observation_id desc)=1
), trip_profile as (
    -- Match original trip codes to the code known at the origin, never to a future GBFS bridge.
    -- Whole-hour groups are withheld until their latest contributing ingestion is available.
    select p.prediction_id,
        sum(if(e.endpoint_type='departure',e.endpoint_count,null)) as observed_departures_matching_hour_lookback,
        sum(if(e.endpoint_type='arrival',e.endpoint_count,null)) as observed_arrivals_matching_hour_lookback,
        count(distinct date(e.hour_at_utc,'America/New_York')) as trip_history_observed_dates,
        max(e.latest_source_ingested_at_utc) as trip_history_available_at_utc,
        max(e.hour_at_utc) as trip_history_latest_event_hour_utc
    from requests p left join {{ ref('int_trip_endpoints_hourly') }} e
      on p.origin_trip_station_id=e.trip_station_id
      and e.latest_source_ingested_at_utc<=p.prediction_at_utc
      and e.hour_at_utc>=timestamp_sub(p.prediction_at_utc,interval {{ var('availability_trip_lookback_days') }} day)
      and timestamp_add(e.hour_at_utc,interval 1 hour)<=p.prediction_at_utc
      and extract(hour from datetime(e.hour_at_utc,'America/New_York'))=p.target_local_hour
      and extract(dayofweek from date(e.hour_at_utc,'America/New_York'))=p.target_local_day_of_week
    group by p.prediction_id
), weather as (
    select p.prediction_id,w.weather_record_id,w.weather_at_utc,w.available_at_utc as weather_available_at_utc,
        w.forecast_fetched_at_utc as weather_fetched_at_utc,
        w.temperature_c,w.humidity_pct,w.precipitation_mm,w.wind_speed_kmh
    from requests p left join {{ ref('stg_weather') }} w
      on w.weather_at_utc=p.target_hour_utc and w.source_type='forecast_api'
      and w.available_at_utc<=p.prediction_at_utc
      and w.is_future_at_available_time and w.weather_at_utc>p.prediction_at_utc
    qualify row_number() over(partition by p.prediction_id
        order by w.available_at_utc desc,w.forecast_fetched_at_utc desc,w.weather_record_id desc)=1
)
select p.prediction_id,p.station_id,p.origin_observation_id,p.origin_snapshot_id,
    p.prediction_at_utc,p.target_at_utc,p.target_hour_utc,p.horizon_minutes,p.label_tolerance_minutes,
    p.target_at_local,p.target_local_hour,p.target_local_day_of_week,p.target_is_weekend,
    {{ var('availability_lag_minutes') }} as lag_minutes, {{ var('availability_trip_lookback_days') }} as trip_lookback_days,
    p.is_origin_usable,p.origin_available_at_utc,p.origin_reported_at_utc,p.origin_metadata_available_at_utc,
    p.origin_trip_station_id,
    if(p.is_origin_usable,p.origin_bikes_available,null) as origin_bikes_available,
    if(p.is_origin_usable,p.origin_docks_available,null) as origin_docks_available,
    if(p.is_origin_usable,p.origin_capacity,null) as origin_capacity,
    if(p.is_origin_usable,p.origin_bike_fill_ratio,null) as origin_bike_fill_ratio,
    if(p.is_origin_usable,p.origin_report_age_seconds,null) as origin_report_age_seconds,
    l.lag_observation_id,l.lag_available_at_utc,l.lag_reported_at_utc,l.has_lag_inventory,
    if(l.has_lag_inventory,l.lag_bikes,null) as bikes_available_lag,
    t.observed_departures_matching_hour_lookback,t.observed_arrivals_matching_hour_lookback,
    t.trip_history_observed_dates,t.trip_history_available_at_utc,t.trip_history_latest_event_hour_utc,
    t.trip_history_observed_dates>0 as has_trip_history,
    w.weather_record_id,w.weather_at_utc,w.weather_available_at_utc,w.weather_fetched_at_utc,
    w.weather_record_id is not null as has_forecast_weather,
    w.temperature_c as forecast_temperature_c,w.humidity_pct as forecast_humidity_pct,
    w.precipitation_mm as forecast_precipitation_mm,w.wind_speed_kmh as forecast_wind_speed_kmh
from requests p join lagged l using(prediction_id) join trip_profile t using(prediction_id) join weather w using(prediction_id)
