{{ config(tags=['inventory_history']) }}
with failures as (
    select 'business_key' as problem from {{ ref('fct_station_inventory_history') }}
    group by station_id,snapshot_id having count(*) != 1
    union all
    select 'unusable_binary_observation' from {{ ref('fct_station_inventory_history') }}
    where (not is_bike_observation_usable and has_bike_observed_strict is not null)
       or (not is_dock_observation_usable and has_dock_observed_strict is not null)
       or (is_bike_observation_usable and (has_bike_observed_strict is distinct from (bikes_available>=1)))
       or (is_dock_observation_usable and (has_dock_observed_strict is distinct from (docks_available>=1)))
    union all
    select 'unsafe_eligible_observation' from {{ ref('fct_station_inventory_history') }}
    where (is_bike_observation_usable or is_dock_observation_usable)
      and (report_time_quality != 'valid' or report_age_seconds < 0
           or inventory_counts_quality != 'valid' or capacity_check != 'within_known_capacity'
           or reported_at_utc is null or metadata_available_at_utc is null)
    union all
    select 'operational_flag' from {{ ref('fct_station_inventory_history') }}
    where (is_bike_observation_usable and is_renting is distinct from true)
       or (is_dock_observation_usable and is_returning is distinct from true)
    union all
    select 'collection_time' from {{ ref('fct_station_inventory_history') }}
    where source_available_at_utc != snapshot_at_utc
       or collection_local_date != date(snapshot_at_utc,'America/New_York')
       or collected_hour_utc != timestamp_trunc(snapshot_at_utc,hour)
       or seconds_since_previous_collection < 0
       or (previous_snapshot_at_utc is not null and seconds_since_previous_collection is distinct from timestamp_diff(snapshot_at_utc,previous_snapshot_at_utc,second))
    union all
    select 'capacity_ratio' from {{ ref('fct_station_inventory_history') }}
    where bike_fill_ratio not between 0 and 1 or dock_fill_ratio not between 0 and 1
       or (capacity_check != 'within_known_capacity' and (bike_fill_ratio is not null or dock_fill_ratio is not null))
)
select * from failures
