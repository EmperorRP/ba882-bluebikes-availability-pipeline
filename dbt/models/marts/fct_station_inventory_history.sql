{{ config(materialized='table', schema='marts', tags=['inventory_history'],
    partition_by={'field': 'snapshot_at_utc', 'data_type': 'timestamp', 'granularity': 'day'},
    cluster_by=['station_id']) }}
-- Preserve the station/snapshot grain; never forward-fill unobserved periods.
with metadata_asof as (
    select s.*, i.trip_station_id as trip_station_id_at_collection,
        i.station_name as station_name_at_collection,
        i.capacity as capacity_at_collection,
        i.snapshot_at_utc as metadata_available_at_utc,
        i.snapshot_id as metadata_snapshot_id
    from {{ ref('stg_station_status') }} s
    left join {{ ref('stg_station_information') }} i
      on s.station_id = i.station_id and i.snapshot_at_utc <= s.snapshot_at_utc
    qualify row_number() over (
        partition by s.station_id, s.snapshot_id
        order by i.snapshot_at_utc desc, i.snapshot_id desc
    ) = 1
), quality as (
    select *,
        case when bikes_available is null or docks_available is null then 'missing_counts'
             when bikes_available < 0 or docks_available < 0 then 'negative_counts'
             else 'valid' end as inventory_counts_quality,
        case when capacity_at_collection is null then 'unknown_capacity'
             when capacity_at_collection <= 0 then 'nonpositive_capacity'
             when bikes_available is null or docks_available is null
                  or bikes_available < 0 or docks_available < 0 then 'invalid_counts'
             when bikes_available + docks_available > capacity_at_collection then 'exceeds_known_capacity'
             else 'within_known_capacity' end as capacity_check,
        lag(snapshot_at_utc) over station_history as previous_snapshot_at_utc,
        lag(reported_at_utc) over station_history as previous_reported_at_utc
    from metadata_asof
    window station_history as (partition by station_id order by snapshot_at_utc, snapshot_id)
), eligible as (
    select *,
        coalesce(report_time_quality = 'valid' and report_age_seconds >= 0
            and inventory_counts_quality = 'valid' and capacity_check = 'within_known_capacity'
            and is_renting and station_id is not null and snapshot_id is not null, false)
            as is_bike_observation_usable,
        coalesce(report_time_quality = 'valid' and report_age_seconds >= 0
            and inventory_counts_quality = 'valid' and capacity_check = 'within_known_capacity'
            and is_returning and station_id is not null and snapshot_id is not null, false)
            as is_dock_observation_usable
    from quality
)
select to_hex(sha256(to_json_string(struct(station_id, snapshot_id)))) as inventory_observation_id,
    *, snapshot_at_utc as source_available_at_utc,
    timestamp_trunc(snapshot_at_utc, hour) as collected_hour_utc,
    date(snapshot_at_utc, 'America/New_York') as collection_local_date,
    timestamp_diff(snapshot_at_utc, previous_snapshot_at_utc, second) as seconds_since_previous_collection,
    case when report_time_quality = 'valid' then reported_at_utc = previous_reported_at_utc end
        as is_repeated_station_report,
    case when report_time_quality = 'valid' then reported_at_utc < previous_reported_at_utc end
        as report_time_regressed,
    case when is_bike_observation_usable then bikes_available >= 1 end as has_bike_observed_strict,
    case when is_dock_observation_usable then docks_available >= 1 end as has_dock_observed_strict,
    case when capacity_check = 'within_known_capacity'
        then safe_divide(bikes_available, capacity_at_collection) end as bike_fill_ratio,
    case when capacity_check = 'within_known_capacity'
        then safe_divide(docks_available, capacity_at_collection) end as dock_fill_ratio
from eligible
