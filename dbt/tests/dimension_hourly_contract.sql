{{ config(tags=['dimension_hourly']) }}
with failures as (
    select 'station_hour_grain' as problem from {{ ref('fct_station_hourly_flows') }}
    group by station_id,hour_at_utc having count(*) != 1
    union all
    select 'flow_values' from {{ ref('fct_station_hourly_flows') }}
    where departures < 0 or arrivals < 0 or total_endpoints <= 0
       or net_flow != arrivals - departures or total_endpoints != arrivals + departures
       or hour_at_utc != timestamp_trunc(hour_at_utc, hour)
       or hour_at_local != datetime(hour_at_utc, 'America/New_York')
       or local_date != date(hour_at_utc, 'America/New_York')
       or local_hour != extract(hour from hour_at_local)
       or utc_offset != format_timestamp('%z', hour_at_utc, 'America/New_York')
       or first_source_ingested_at_utc > latest_source_ingested_at_utc
    union all
    select 'endpoint_values' from {{ ref('int_trip_endpoints_hourly') }}
    where endpoint_count <= 0 or hour_at_utc != timestamp_trunc(hour_at_utc,hour)
       or (mapping_status = 'mapped' and (station_id is null or trip_station_id is null))
       or (mapping_status != 'mapped' and station_id is not null)
       or (mapping_status = 'missing_code' and trip_station_id is not null)
       or (mapping_status = 'unmapped_code' and trip_station_id is null)
    union all
    select 'date_continuity' from (
        select count(*) as n, date_diff(max(calendar_date),min(calendar_date),day)+1 as expected_n
        from {{ ref('dim_date') }}
    ) where n != expected_n
    union all
    select 'station_bridge_mismatch' from {{ ref('bridge_station_ids') }} b
    full outer join {{ ref('dim_station') }} d using(station_id)
    where b.station_id is null or d.station_id is null or b.trip_station_id is distinct from d.trip_station_id
)
select * from failures
