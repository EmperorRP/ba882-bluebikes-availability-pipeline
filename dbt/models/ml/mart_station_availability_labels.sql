{{ config(materialized='table', schema='ml', tags=['point_in_time_ml'],
    partition_by={'field':'prediction_at_utc','data_type':'timestamp','granularity':'day'},
    cluster_by=['station_id','horizon_minutes']) }}
-- Earliest qualifying source report at/after target, then earliest availability of that report.
-- A later collection of an OLD report cannot label a future target.
select p.prediction_id,p.station_id,p.prediction_at_utc,p.target_at_utc,p.horizon_minutes,p.label_tolerance_minutes,
    l.inventory_observation_id as label_observation_id,
    l.reported_at_utc as label_reported_at_utc,l.source_available_at_utc as label_available_at_utc,
    timestamp_diff(l.reported_at_utc,p.target_at_utc,second) as label_offset_seconds,
    cast(l.has_bike_observed_strict as int64) as target_has_bike,
    l.bikes_available as target_bikes_available,
    case when l.inventory_observation_id is null then 'no_usable_label_in_window' else 'observed' end as label_status
from {{ ref('int_availability_prediction_requests') }} p
left join {{ ref('fct_station_inventory_history') }} l
  on p.station_id=l.station_id and l.is_bike_observation_usable
  and l.reported_at_utc between p.target_at_utc and timestamp_add(p.target_at_utc,interval p.label_tolerance_minutes minute)
  and l.source_available_at_utc>=p.target_at_utc
  and timestamp_diff(l.source_available_at_utc,l.reported_at_utc,second) between 0 and {{ var('availability_max_report_age_minutes') }}*60
qualify row_number() over(partition by p.prediction_id
    order by l.reported_at_utc,l.source_available_at_utc,l.inventory_observation_id)=1
