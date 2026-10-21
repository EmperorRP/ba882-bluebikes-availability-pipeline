{{ config(tags=['inventory_history'], severity='warn') }}
select snapshot_id,last_collected_at_utc,collection_age_seconds_now
from {{ ref('inventory_collection_quality') }} where is_latest_collection and is_collection_stale_now
