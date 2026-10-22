-- Snapshot identity is station_id + snapshot_id, never the local display time.
{% for model in ['stg_station_information', 'stg_station_status'] %}
select '{{ model }}' as model_name, station_id, snapshot_id, count(*) as record_count
from {{ ref(model) }}
group by station_id, snapshot_id
having count(*) > 1
{% if not loop.last %}union all{% endif %}
{% endfor %}
