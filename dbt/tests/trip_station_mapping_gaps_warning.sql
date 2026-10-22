{{ config(severity='warn') }}
-- Report unknown/missing codes without guessing or dropping trips.
with endpoints as (
    select 'start' as endpoint, nullif(trim(start_station_id), '') as trip_station_id
    from {{ source('bluebikes', 'historical_trips') }}
    union all
    select 'end' as endpoint, nullif(trim(end_station_id), '') as trip_station_id
    from {{ source('bluebikes', 'historical_trips') }}
)
select e.endpoint, e.trip_station_id, count(*) as trip_count
from endpoints e
left join {{ ref('bridge_station_ids') }} b using (trip_station_id)
where b.station_id is null
group by e.endpoint, e.trip_station_id
