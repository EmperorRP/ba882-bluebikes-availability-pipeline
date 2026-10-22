{{ config(tags=['inventory_history'], severity='warn') }}
-- Different GBFS feeds may be sampled seconds apart; preserve and review, never clamp counts.
select inventory_observation_id,station_id,snapshot_at_utc,bikes_available,docks_available,capacity_at_collection
from {{ ref('fct_station_inventory_history') }} where capacity_check = 'exceeds_known_capacity'
