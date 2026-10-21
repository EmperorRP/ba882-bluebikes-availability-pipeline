{{ config(tags=['inventory_history']) }}
with expected as (
    select snapshot_id,count(*) as n,count(distinct station_id) as stations,
        countif(is_bike_observation_usable) as bikes,countif(is_dock_observation_usable) as docks,
        countif(report_time_quality != 'valid') as suspect,
        countif(capacity_check = 'exceeds_known_capacity') as capacity_review,
        countif(is_repeated_station_report) as repeated_reports
    from {{ ref('fct_station_inventory_history') }} group by 1
)
select coalesce(e.snapshot_id,q.snapshot_id) as snapshot_id
from expected e full outer join {{ ref('inventory_collection_quality') }} q using(snapshot_id)
where e.n is distinct from q.observation_count or e.stations is distinct from q.station_count
   or e.bikes is distinct from q.usable_bike_observations or e.docks is distinct from q.usable_dock_observations
   or e.suspect is distinct from q.suspect_report_time_count or e.capacity_review is distinct from q.capacity_review_count
   or e.repeated_reports is distinct from q.repeated_report_count
