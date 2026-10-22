{{ config(tags=['inventory_history']) }}
-- Compare the business key and every preserved source field; fail on loss, additions or changes.
with source_rows as (
    select station_id,snapshot_id,to_json_string(s) as source_row
    from {{ ref('stg_station_status') }} s
), history_rows as (
    select station_id,snapshot_id,
        to_json_string(struct(station_id,snapshot_id,snapshot_at_utc,snapshot_at_local,
            bikes_available,docks_available,is_renting,is_returning,source_last_reported,
            reported_at_utc,report_age_seconds,report_time_quality,is_usable_inventory_observation,
            has_bike_observed,source_url)) as history_row
    from {{ ref('fct_station_inventory_history') }}
)
select coalesce(s.station_id,h.station_id) as station_id,coalesce(s.snapshot_id,h.snapshot_id) as snapshot_id
from source_rows s full outer join history_rows h using(station_id,snapshot_id)
where s.source_row is distinct from h.history_row
