select 'information' as feed, station_id, snapshot_id
from {{ ref('stg_station_information') }}
where capacity < 0 or latitude is null or longitude is null
    or not (latitude between -90 and 90)
    or not (longitude between -180 and 180)
union all
select 'status' as feed, station_id, snapshot_id
from {{ ref('stg_station_status') }}
where bikes_available < 0 or docks_available < 0
    or is_renting is null or is_returning is null
