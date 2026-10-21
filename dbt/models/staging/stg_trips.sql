{{ config(materialized='view', tags=['trip_weather_staging']) }}

-- The current loader stored unzoned CSV clock values as UTC TIMESTAMPs.
-- Recover the clock first, then apply the explicitly documented source timezone.
with normalized as (
    select
        nullif(trim(ride_id), '') as ride_id,
        lower(nullif(trim(rideable_type), '')) as rideable_type,
        lower(nullif(trim(member_casual), '')) as rider_type,
        started_at as raw_started_at, ended_at as raw_ended_at,
        datetime(started_at, 'UTC') as started_at_local,
        datetime(ended_at, 'UTC') as ended_at_local,
        nullif(trim(start_station_id), '') as start_trip_station_id,
        nullif(trim(end_station_id), '') as end_trip_station_id,
        start_station_name, end_station_name,
        start_lat as start_latitude, start_lng as start_longitude,
        end_lat as end_latitude, end_lng as end_longitude,
        ingested_at as ingested_at_utc, gcs_path, source_url, source_checksum
    from {{ source('bluebikes', 'historical_trips') }}
    qualify row_number() over (
        partition by ride_id order by ingested_at desc, source_checksum desc, started_at desc
    ) = 1
), converted as (
    select *,
        timestamp(started_at_local, '{{ var("trip_source_timezone", "America/New_York") }}') as started_at_utc,
        timestamp(ended_at_local, '{{ var("trip_source_timezone", "America/New_York") }}') as ended_at_utc
    from normalized
), quality as (
    select *,
        case
            when started_at_local is null or ended_at_local is null then 'missing_time'
            when datetime(started_at_utc, '{{ var("trip_source_timezone", "America/New_York") }}') != started_at_local
              or datetime(ended_at_utc, '{{ var("trip_source_timezone", "America/New_York") }}') != ended_at_local
                then 'nonexistent_local_time'
            when datetime(timestamp_add(started_at_utc, interval 1 hour), '{{ var("trip_source_timezone", "America/New_York") }}') = started_at_local
              or datetime(timestamp_sub(started_at_utc, interval 1 hour), '{{ var("trip_source_timezone", "America/New_York") }}') = started_at_local
              or datetime(timestamp_add(ended_at_utc, interval 1 hour), '{{ var("trip_source_timezone", "America/New_York") }}') = ended_at_local
              or datetime(timestamp_sub(ended_at_utc, interval 1 hour), '{{ var("trip_source_timezone", "America/New_York") }}') = ended_at_local
                then 'ambiguous_local_time'
            when ended_at_utc < started_at_utc then 'negative_duration'
            else 'valid'
        end as trip_time_quality
    from converted
)
select
    t.*,
    '{{ var("trip_source_timezone", "America/New_York") }}' as source_timezone,
    'inferred_from_unzoned_csv_and_dst_pattern' as timezone_basis,
    timestamp_diff(ended_at_utc, started_at_utc, microsecond) / 1000000.0 as duration_seconds,
    timestamp_trunc(started_at_utc, hour) as started_hour_utc,
    timestamp_trunc(ended_at_utc, hour) as ended_hour_utc,
    s.station_id as start_station_id,
    e.station_id as end_station_id,
    case when start_trip_station_id is null then 'missing_code'
         when s.station_id is null then 'unmapped_code' else 'mapped' end as start_mapping_status,
    case when end_trip_station_id is null then 'missing_code'
         when e.station_id is null then 'unmapped_code' else 'mapped' end as end_mapping_status
from quality t
left join {{ ref('bridge_station_ids') }} s on t.start_trip_station_id = s.trip_station_id
left join {{ ref('bridge_station_ids') }} e on t.end_trip_station_id = e.trip_station_id
