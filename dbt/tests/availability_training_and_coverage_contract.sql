{{ config(tags=['point_in_time_ml']) }}
with expected as (
    select f.prediction_id from {{ ref('mart_station_availability_features') }} f
    join {{ ref('mart_station_availability_labels') }} l using(prediction_id)
    where f.is_origin_usable and l.target_has_bike is not null
), actual as (select prediction_id from {{ ref('station_availability_training_ready') }})
select 'training_membership' as problem from expected e full outer join actual a using(prediction_id)
where e.prediction_id is null or a.prediction_id is null
union all
select 'coverage_count' from {{ ref('availability_sample_coverage') }} c
where c.prediction_requests!=(select count(*) from {{ ref('mart_station_availability_features') }} f where f.horizon_minutes=c.horizon_minutes)
   or c.training_eligible_requests!=(select count(*) from {{ ref('station_availability_training_ready') }} t where t.horizon_minutes=c.horizon_minutes)
