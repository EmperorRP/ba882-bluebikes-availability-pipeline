{{ config(materialized='view', tags=['station_foundation']) }}

-- Latest-known metadata mapping. Not a point-in-time historical dimension.
-- Historical mapping stability and both ID uniqueness constraints are tested.
select
    station_id,
    trip_station_id,
    station_name,
    min(snapshot_at_utc) over (partition by station_id) as first_observed_at_utc,
    snapshot_at_utc as latest_metadata_at_utc,
    snapshot_id as latest_snapshot_id
from {{ ref('stg_station_information') }}
qualify row_number() over (
    partition by station_id
    order by snapshot_at_utc desc, snapshot_id desc
) = 1
