{{ config(tags=['dimension_hourly']) }}
with expected as (
    select station_id, hour_at_utc,
        sum(if(endpoint_type = 'departure', endpoint_count, 0)) as departures,
        sum(if(endpoint_type = 'arrival', endpoint_count, 0)) as arrivals
    from {{ ref('int_trip_endpoints_hourly') }} where mapping_status = 'mapped'
    group by 1,2
)
select coalesce(e.station_id,a.station_id) as station_id, coalesce(e.hour_at_utc,a.hour_at_utc) as hour_at_utc
from expected e full outer join {{ ref('fct_station_hourly_flows') }} a using(station_id,hour_at_utc)
where e.departures is distinct from a.departures or e.arrivals is distinct from a.arrivals
