{{ config(tags=['point_in_time_ml']) }}
with expected as (
    select h.inventory_observation_id,horizon_minutes
    from {{ ref('fct_station_inventory_history') }} h
    cross join unnest([{{ var('availability_horizons_minutes') | join(',') }}]) as horizon_minutes
)
select coalesce(e.inventory_observation_id,p.origin_observation_id) as origin_id
from expected e full outer join {{ ref('int_availability_prediction_requests') }} p
  on e.inventory_observation_id=p.origin_observation_id and e.horizon_minutes=p.horizon_minutes
where e.inventory_observation_id is null or p.prediction_id is null
union all
select p.origin_observation_id from {{ ref('int_availability_prediction_requests') }} p
left join {{ ref('mart_station_availability_features') }} f using(prediction_id)
left join {{ ref('mart_station_availability_labels') }} l using(prediction_id)
where f.prediction_id is null or l.prediction_id is null
