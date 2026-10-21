{{ config(tags=['point_in_time_ml']) }}
select prediction_id from {{ ref('mart_station_availability_labels') }}
where (label_status='no_usable_label_in_window' and (target_has_bike is not null or label_observation_id is not null or target_bikes_available is not null))
   or (label_status='observed' and (target_has_bike is null or label_observation_id is null or target_bikes_available is null
       or label_reported_at_utc<target_at_utc or label_reported_at_utc>timestamp_add(target_at_utc,interval label_tolerance_minutes minute)
       or label_available_at_utc<label_reported_at_utc
       or target_has_bike is distinct from cast(target_bikes_available>=1 as int64)))
