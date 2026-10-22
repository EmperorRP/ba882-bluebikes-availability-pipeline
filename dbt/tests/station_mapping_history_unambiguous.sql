with pairs as (
    select distinct station_id, trip_station_id
    from {{ ref('stg_station_information') }}
)
select 'trip_to_gbfs' as direction, trip_station_id as identifier
from pairs
group by trip_station_id
having count(distinct station_id) > 1
union all
select 'gbfs_to_trip' as direction, station_id as identifier
from pairs
group by station_id
having count(distinct trip_station_id) > 1
