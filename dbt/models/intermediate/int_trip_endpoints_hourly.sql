{{ config(materialized='table', schema='intermediate', tags=['dimension_hourly'],
    partition_by={'field': 'hour_at_utc', 'data_type': 'timestamp', 'granularity': 'day'},
    cluster_by=['station_id', 'mapping_status', 'endpoint_type']) }}
-- Each valid trip contributes one departure AND one arrival, even if its station is unknown.
with endpoints as (
    select started_hour_utc as hour_at_utc, 'departure' as endpoint_type,
        start_station_id as station_id, start_trip_station_id as trip_station_id,
        start_mapping_status as mapping_status, ingested_at_utc
    from {{ ref('stg_trips') }} where trip_time_quality = 'valid'
    union all
    select ended_hour_utc, 'arrival', end_station_id, end_trip_station_id,
        end_mapping_status, ingested_at_utc
    from {{ ref('stg_trips') }} where trip_time_quality = 'valid'
), grouped as (
    select hour_at_utc, endpoint_type, station_id, trip_station_id, mapping_status,
        count(*) as endpoint_count,
        min(ingested_at_utc) as first_source_ingested_at_utc,
        max(ingested_at_utc) as latest_source_ingested_at_utc
    from endpoints group by 1,2,3,4,5
)
select to_hex(sha256(to_json_string(struct(hour_at_utc, endpoint_type, station_id, trip_station_id, mapping_status)))) as endpoint_hour_id,
    * from grouped
