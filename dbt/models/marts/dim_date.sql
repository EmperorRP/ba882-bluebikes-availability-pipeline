{{ config(materialized='table', schema='marts', tags=['dimension_hourly']) }}
-- A calendar spanning observed source dates. Its presence does not prove data coverage.
with observed_dates as (
    select date(started_at_local) as source_date from {{ ref('stg_trips') }}
    union all select date(ended_at_local) from {{ ref('stg_trips') }}
    union all select date(snapshot_at_local) from {{ ref('stg_station_information') }}
    union all select date(snapshot_at_local) from {{ ref('stg_station_status') }}
    union all select date(weather_at_utc, 'America/New_York') from {{ ref('stg_weather') }}
), bounds as (
    select min(source_date) as first_date, max(source_date) as last_date from observed_dates
), calendar as (
    select calendar_date from bounds, unnest(generate_date_array(first_date, last_date)) as calendar_date
)
select calendar_date, cast(format_date('%Y%m%d', calendar_date) as int64) as date_key,
    extract(year from calendar_date) as calendar_year,
    extract(quarter from calendar_date) as calendar_quarter,
    extract(month from calendar_date) as calendar_month,
    extract(day from calendar_date) as day_of_month,
    extract(dayofweek from calendar_date) as day_of_week_sunday_1,
    format_date('%A', calendar_date) as day_name,
    extract(isoyear from calendar_date) as iso_year,
    extract(isoweek from calendar_date) as iso_week,
    date_trunc(calendar_date, week(monday)) as week_start_date,
    date_trunc(calendar_date, month) as month_start_date,
    extract(dayofweek from calendar_date) in (1, 7) as is_weekend
from calendar
