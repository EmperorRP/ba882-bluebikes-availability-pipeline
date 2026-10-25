{{ config(severity='warn') }}
-- Preserve these source observations, but surface them before downstream use.
select station_id, snapshot_id, source_last_reported, report_time_quality
from {{ ref('stg_station_status') }}
where report_time_quality != 'valid'
