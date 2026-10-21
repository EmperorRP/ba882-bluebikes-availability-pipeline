{% macro validate_availability_policy() %}
{% set horizons = var('availability_horizons_minutes') %}
{% if horizons | length == 0 or horizons | unique | list | length != horizons | length %}
  {{ exceptions.raise_compiler_error('Availability horizons must be nonempty and unique.') }}
{% endif %}
{% for h in horizons %}
  {% if h is not number or h != h | int or h < 1 or h > 1440 %}
    {{ exceptions.raise_compiler_error('Availability horizons must be integer minutes from 1 to 1440.') }}
  {% endif %}
{% endfor %}
{% for name in ['availability_label_tolerance_minutes','availability_max_report_age_minutes','availability_trip_lookback_days','availability_lag_minutes'] %}
  {% set value = var(name) %}
  {% if value is not number or value != value | int or value < 1 %}
    {{ exceptions.raise_compiler_error(name ~ ' must be a positive integer.') }}
  {% endif %}
{% endfor %}
{% endmacro %}
