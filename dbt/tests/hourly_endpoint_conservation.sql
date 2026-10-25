{{ config(tags=['dimension_hourly']) }}
-- Independently recompute every raw-code/hour endpoint group from staging.
with expected as (
    select hour_at_utc, endpoint_type, station_id, trip_station_id, mapping_status, count(*) as n
    from (
        select started_hour_utc as hour_at_utc, 'departure' as endpoint_type,
            start_station_id as station_id, start_trip_station_id as trip_station_id, start_mapping_status as mapping_status
        from {{ ref('stg_trips') }} where trip_time_quality = 'valid'
        union all
        select ended_hour_utc, 'arrival', end_station_id, end_trip_station_id, end_mapping_status
        from {{ ref('stg_trips') }} where trip_time_quality = 'valid'
    ) group by 1,2,3,4,5
), compared as (
    select coalesce(e.hour_at_utc, a.hour_at_utc) as hour_at_utc,
        e.n as expected_count, a.endpoint_count as actual_count
    from expected e full outer join {{ ref('int_trip_endpoints_hourly') }} a
      on e.hour_at_utc = a.hour_at_utc and e.endpoint_type = a.endpoint_type
      and e.station_id is not distinct from a.station_id
      and e.trip_station_id is not distinct from a.trip_station_id
      and e.mapping_status = a.mapping_status
)
select * from compared where expected_count is distinct from actual_count
