{{ config(materialized='table', schema='marts', tags=['dimension_hourly'],
    partition_by={'field': 'hour_at_utc', 'data_type': 'timestamp', 'granularity': 'day'},
    cluster_by=['station_id']) }}
-- Sparse observed event hours only. Missing rows do not imply zero activity.
with flows as (
    select station_id, hour_at_utc,
        sum(if(endpoint_type = 'departure', endpoint_count, 0)) as departures,
        sum(if(endpoint_type = 'arrival', endpoint_count, 0)) as arrivals,
        min(first_source_ingested_at_utc) as first_source_ingested_at_utc,
        max(latest_source_ingested_at_utc) as latest_source_ingested_at_utc
    from {{ ref('int_trip_endpoints_hourly') }}
    where mapping_status = 'mapped'
    group by station_id, hour_at_utc
)
select to_hex(sha256(to_json_string(struct(station_id, hour_at_utc)))) as station_hour_id,
    *, datetime(hour_at_utc, 'America/New_York') as hour_at_local,
    date(hour_at_utc, 'America/New_York') as local_date,
    extract(hour from datetime(hour_at_utc, 'America/New_York')) as local_hour,
    format_timestamp('%z', hour_at_utc, 'America/New_York') as utc_offset,
    arrivals - departures as net_flow,
    arrivals + departures as total_endpoints
from flows
