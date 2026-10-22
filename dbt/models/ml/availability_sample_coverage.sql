{{ config(materialized='view', schema='ml', tags=['point_in_time_ml']) }}
select f.horizon_minutes,count(*) as prediction_requests,
    countif(f.is_origin_usable) as usable_origin_requests,
    countif(f.has_lag_inventory) as requests_with_lag_inventory,
    countif(f.has_trip_history) as requests_with_trip_history,
    countif(f.has_forecast_weather) as requests_with_forecast_weather,
    countif(l.target_has_bike is not null) as labelled_requests,
    countif(f.is_origin_usable and l.target_has_bike is not null) as training_eligible_requests,
    count(distinct if(f.is_origin_usable and l.target_has_bike is not null,f.prediction_at_utc,null)) as labelled_origin_times,
    countif(l.label_status='no_usable_label_in_window') as requests_missing_labels,
    min(f.prediction_at_utc) as first_prediction_at_utc,max(f.prediction_at_utc) as last_prediction_at_utc
from {{ ref('mart_station_availability_features') }} f
join {{ ref('mart_station_availability_labels') }} l using(prediction_id)
group by f.horizon_minutes
