{{ config(materialized='table', schema='marts', tags=['dimension_hourly']) }}
-- Latest observed metadata, not a historical/as-of dimension.
with ranked as (
    select *, min(snapshot_at_utc) over (partition by station_id) as first_observed_at_utc,
        row_number() over (partition by station_id order by snapshot_at_utc desc, snapshot_id desc) as metadata_rank
    from {{ ref('stg_station_information') }}
)
select station_id, trip_station_id, station_name, latitude, longitude, capacity,
    first_observed_at_utc, snapshot_at_utc as latest_metadata_at_utc,
    snapshot_id as latest_snapshot_id, source_url
from ranked where metadata_rank = 1
