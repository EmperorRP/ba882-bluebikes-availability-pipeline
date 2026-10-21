{{ config(tags=['inventory_history']) }}
select h.inventory_observation_id
from {{ ref('fct_station_inventory_history') }} h
where h.metadata_available_at_utc > h.snapshot_at_utc
   or exists (
       select 1 from {{ ref('stg_station_information') }} i
       where i.station_id = h.station_id and i.snapshot_at_utc <= h.snapshot_at_utc
         and (h.metadata_available_at_utc is null or i.snapshot_at_utc > h.metadata_available_at_utc
              or (i.snapshot_at_utc = h.metadata_available_at_utc and i.snapshot_id > h.metadata_snapshot_id))
   )
   or (h.metadata_available_at_utc is not null and not exists (
       select 1 from {{ ref('stg_station_information') }} i
       where i.station_id = h.station_id and i.snapshot_id = h.metadata_snapshot_id
         and i.snapshot_at_utc = h.metadata_available_at_utc
         and i.capacity is not distinct from h.capacity_at_collection
         and i.station_name is not distinct from h.station_name_at_collection
         and i.trip_station_id is not distinct from h.trip_station_id_at_collection
   ))
