{{ config(materialized='view', schema='intermediate', tags=['point_in_time_ml']) }}
{{ validate_availability_policy() }}
with requests as (
    select h.inventory_observation_id as origin_observation_id, h.station_id,
        h.snapshot_id as origin_snapshot_id, h.snapshot_at_utc as prediction_at_utc,
        h.reported_at_utc as origin_reported_at_utc,
        h.source_available_at_utc as origin_available_at_utc,
        h.metadata_available_at_utc as origin_metadata_available_at_utc,
        h.trip_station_id_at_collection as origin_trip_station_id,
        h.capacity_at_collection as origin_capacity,
        h.bikes_available as origin_bikes_available, h.docks_available as origin_docks_available,
        h.bike_fill_ratio as origin_bike_fill_ratio, h.report_age_seconds as origin_report_age_seconds,
        coalesce(h.is_bike_observation_usable and h.report_age_seconds between 0 and {{ var('availability_max_report_age_minutes') }} * 60, false) as is_origin_usable,
        horizon_minutes,
        {{ var('availability_label_tolerance_minutes') }} as label_tolerance_minutes,
        timestamp_add(h.snapshot_at_utc, interval horizon_minutes minute) as target_at_utc
    from {{ ref('fct_station_inventory_history') }} h
    cross join unnest([{{ var('availability_horizons_minutes') | join(',') }}]) as horizon_minutes
)
select to_hex(sha256(to_json_string(struct(origin_observation_id,horizon_minutes)))) as prediction_id,
    *, timestamp_trunc(target_at_utc,hour) as target_hour_utc,
    datetime(target_at_utc,'America/New_York') as target_at_local,
    extract(hour from datetime(target_at_utc,'America/New_York')) as target_local_hour,
    extract(dayofweek from date(target_at_utc,'America/New_York')) as target_local_day_of_week,
    extract(dayofweek from date(target_at_utc,'America/New_York')) in (1,7) as target_is_weekend
from requests
