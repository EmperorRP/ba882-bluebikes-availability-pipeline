{{ config(tags=['point_in_time_ml'],severity='warn') }}
select horizon_minutes,prediction_requests,training_eligible_requests,labelled_origin_times
from {{ ref('availability_sample_coverage') }} where training_eligible_requests=0
