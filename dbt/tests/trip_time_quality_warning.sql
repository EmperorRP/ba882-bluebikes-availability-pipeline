{{ config(severity='warn') }}
select ride_id, raw_started_at, raw_ended_at, trip_time_quality
from {{ ref('stg_trips') }}
where trip_time_quality != 'valid'
