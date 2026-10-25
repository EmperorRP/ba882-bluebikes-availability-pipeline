{{ config(tags=['point_in_time_ml']) }}
with eligible as (
    select p.prediction_id,w.weather_record_id,w.available_at_utc,w.forecast_fetched_at_utc
    from {{ ref('int_availability_prediction_requests') }} p join {{ ref('stg_weather') }} w
      on w.weather_at_utc=p.target_hour_utc and w.source_type='forecast_api'
      and w.is_future_at_available_time and w.weather_at_utc>p.prediction_at_utc
      and w.available_at_utc<=p.prediction_at_utc
)
select f.prediction_id from {{ ref('mart_station_availability_features') }} f
where exists (select 1 from eligible e where e.prediction_id=f.prediction_id and
    (f.weather_record_id is null or e.available_at_utc>f.weather_available_at_utc
       or (e.available_at_utc=f.weather_available_at_utc and e.forecast_fetched_at_utc>f.weather_fetched_at_utc)))
   or (f.weather_record_id is not null and not exists (
       select 1 from eligible e where e.prediction_id=f.prediction_id and e.weather_record_id=f.weather_record_id
   ))
