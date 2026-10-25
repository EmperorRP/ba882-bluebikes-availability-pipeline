{{ config(materialized='view', schema='marts', tags=['inventory_history']) }}
-- Age is evaluated at query time. Historical usability is evaluated at collection time.
with batches as (
    select snapshot_id, min(snapshot_at_utc) as first_collected_at_utc,
        max(snapshot_at_utc) as last_collected_at_utc,
        count(*) as observation_count, count(distinct station_id) as station_count,
        countif(is_bike_observation_usable) as usable_bike_observations,
        countif(is_dock_observation_usable) as usable_dock_observations,
        countif(report_time_quality != 'valid') as suspect_report_time_count,
        countif(capacity_check = 'exceeds_known_capacity') as capacity_review_count,
        countif(metadata_available_at_utc is null) as missing_prior_metadata_count,
        countif(is_repeated_station_report) as repeated_report_count,
        countif(report_time_regressed) as regressed_report_count,
        max(seconds_since_previous_collection) as largest_station_collection_gap_seconds
    from {{ ref('fct_station_inventory_history') }} group by snapshot_id
)
select *, last_collected_at_utc = max(last_collected_at_utc) over () as is_latest_collection,
    timestamp_diff(current_timestamp(), last_collected_at_utc, second) as collection_age_seconds_now,
    current_timestamp() > timestamp_add(last_collected_at_utc, interval 120 minute) as is_collection_stale_now
from batches
