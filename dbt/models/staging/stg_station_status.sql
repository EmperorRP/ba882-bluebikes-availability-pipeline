{{ config(materialized='view', tags=['station_foundation']) }}

with normalized as (
    select
        nullif(trim(station_id), '') as station_id,
        nullif(trim(snapshot_id), '') as snapshot_id,
        safe_cast(num_bikes_available as int64) as bikes_available,
        safe_cast(num_docks_available as int64) as docks_available,
        case when is_renting in (0, 1) then is_renting = 1 end as is_renting,
        case when is_returning in (0, 1) then is_returning = 1 end as is_returning,
        safe_cast(last_reported as int64) as source_last_reported,
        ingested_at_utc as snapshot_at_utc,
        source_url,
        raw_json
    from {{ source('bluebikes', 'station_status') }}
    qualify row_number() over (
        partition by station_id, snapshot_id
        order by ingested_at_utc desc, raw_json desc
    ) = 1
), timestamps as (
    select *,
        case when source_last_reported between 0 and 253402300799
            then timestamp_seconds(source_last_reported)
        end as reported_at_utc
    from normalized
), quality as (
    select *,
        timestamp_diff(snapshot_at_utc, reported_at_utc, second) as report_age_seconds,
        case
            when reported_at_utc is null or reported_at_utc < timestamp('2020-01-01')
                then 'invalid_timestamp'
            when reported_at_utc > timestamp_add(snapshot_at_utc, interval 5 minute)
                then 'future_report'
            when reported_at_utc < timestamp_sub(snapshot_at_utc, interval 60 minute)
                then 'stale_report'
            else 'valid'
        end as report_time_quality
    from timestamps
), observations as (
    select *,
        coalesce(
            report_time_quality = 'valid'
            and is_renting
            and bikes_available >= 0 and docks_available >= 0
            and station_id is not null and snapshot_at_utc is not null,
            false
        ) as is_usable_inventory_observation
    from quality
)
select
    station_id, snapshot_id, snapshot_at_utc,
    datetime(snapshot_at_utc, 'America/New_York') as snapshot_at_local,
    bikes_available, docks_available, is_renting, is_returning,
    source_last_reported, reported_at_utc, report_age_seconds,
    report_time_quality, is_usable_inventory_observation,
    case when is_usable_inventory_observation then bikes_available >= 1 end
        as has_bike_observed,
    source_url
from observations
