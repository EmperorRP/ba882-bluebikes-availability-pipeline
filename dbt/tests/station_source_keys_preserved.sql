-- Compare business keys in both directions, so filtering cannot hide source rows.
{% for feed in ['information', 'status'] %}
select '{{ feed }}_missing' as discrepancy, station_id, snapshot_id
from (
    select nullif(trim(station_id), '') as station_id,
           nullif(trim(snapshot_id), '') as snapshot_id
    from {{ source('bluebikes', 'station_' ~ feed) }}
    except distinct
    select station_id, snapshot_id from {{ ref('stg_station_' ~ feed) }}
)
union all
select '{{ feed }}_unexpected' as discrepancy, station_id, snapshot_id
from (
    select station_id, snapshot_id from {{ ref('stg_station_' ~ feed) }}
    except distinct
    select nullif(trim(station_id), ''), nullif(trim(snapshot_id), '')
    from {{ source('bluebikes', 'station_' ~ feed) }}
)
{% if not loop.last %}union all{% endif %}
{% endfor %}
