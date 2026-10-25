{{ config(materialized='view', tags=['station_foundation']) }}

with normalized as (
    select
        nullif(trim(station_id), '') as station_id,
        nullif(trim(snapshot_id), '') as snapshot_id,
        nullif(trim(json_value(raw_json, '$.short_name')), '') as trip_station_id,
        nullif(trim(name), '') as station_name,
        safe_cast(lat as float64) as latitude,
        safe_cast(lon as float64) as longitude,
        safe_cast(capacity as int64) as capacity,
        ingested_at_utc as snapshot_at_utc,
        source_url,
        raw_json
    from {{ source('bluebikes', 'station_information') }}
)
select
    station_id, snapshot_id, trip_station_id, station_name,
    latitude, longitude, capacity, snapshot_at_utc,
    datetime(snapshot_at_utc, 'America/New_York') as snapshot_at_local,
    source_url
from normalized
qualify row_number() over (
    partition by station_id, snapshot_id
    order by snapshot_at_utc desc, raw_json desc
) = 1
