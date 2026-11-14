-- Chronological train / val / test split for one horizon (${horizon_minutes} min).
--   test  = origins in the last ${test_hours}h of available labelled data
--   val   = ${val_hours}h of origins whose labels close before test begins
--   train = rows whose labels close before val begins
-- Gaps between the sets equal horizon + label tolerance, so no label used for
-- fitting is observed after the first origin of the next set.
declare gap_minutes int64 default ${horizon_minutes} + ${label_tolerance_minutes};
declare last_origin timestamp default (
  select max(prediction_at_utc) from `${project}.${source}` where horizon_minutes = ${horizon_minutes});
declare test_start timestamp default timestamp_sub(last_origin, interval ${test_hours} hour);
declare val_end timestamp default timestamp_sub(test_start, interval gap_minutes minute);
declare val_start timestamp default timestamp_sub(val_end, interval ${val_hours} hour);

create or replace table `${project}.${dataset}.split_h${horizon_minutes}`
options (description = 'Chronological split for horizon ${horizon_minutes} min; label no_bike = 1 means zero bikes at target time')
as
with base as (
select * from (
  select
    case
      when prediction_at_utc >= test_start then 'test'
      when prediction_at_utc >= val_start and prediction_at_utc < val_end then 'val'
      when target_at_utc < timestamp_sub(val_start, interval ${label_tolerance_minutes} minute) then 'train'
    end as split,
    prediction_id,
    prediction_at_utc,
    target_at_utc,
    1 - target_has_bike as no_bike,
    station_id,
    target_local_hour,
    cast(target_local_hour as string) as target_hour_cat,
    target_local_day_of_week,
    cast(target_local_day_of_week as string) as target_dow_cat,
    cast(target_is_weekend as int64) as target_is_weekend,
    origin_bikes_available,
    cast(origin_bikes_available = 0 as int64) as origin_no_bike,
    origin_docks_available,
    origin_capacity,
    origin_bike_fill_ratio,
    origin_report_age_seconds,
    bikes_available_lag,
    origin_bikes_available - bikes_available_lag as bikes_change_lag,
    cast(has_lag_inventory as int64) as has_lag_inventory,
    observed_departures_matching_hour_lookback,
    observed_arrivals_matching_hour_lookback,
    safe_divide(observed_arrivals_matching_hour_lookback - observed_departures_matching_hour_lookback,
                trip_history_observed_dates) as net_inflow_per_day_lookback,
    trip_history_observed_dates,
    cast(has_trip_history as int64) as has_trip_history,
    forecast_temperature_c,
    forecast_humidity_pct,
    forecast_precipitation_mm,
    forecast_wind_speed_kmh
  from `${project}.${source}`
  where horizon_minutes = ${horizon_minutes}
)
where split is not null
),
-- Station history features (point-in-time): built from hourly inventory summaries whose hour
-- has fully ended by the prediction time, so nothing after the origin leaks in.
hourly as (
  select station_id,
    timestamp_trunc(snapshot_at_utc, hour) as hour_utc,
    extract(hour from datetime(snapshot_at_utc, 'America/New_York')) as local_hour,
    extract(dayofweek from datetime(snapshot_at_utc, 'America/New_York')) in (1, 7) as is_weekend,
    avg(if(bikes_available = 0, 1, 0)) as empty_frac,
    avg(bikes_available) as mean_bikes
  from `${project}.marts.fct_station_inventory_history`
  where is_usable_inventory_observation
  group by 1, 2, 3, 4
),
same_hour as (
  -- How this station behaved at the target's local hour on earlier days.
  select b.prediction_id,
    avg(h.empty_frac) as hist_empty_rate_target_hour,
    avg(if(h.hour_utc >= timestamp_sub(b.prediction_at_utc, interval 7 day), h.empty_frac, null)) as hist_empty_rate_target_hour_7d,
    avg(if(h.is_weekend = (b.target_is_weekend = 1), h.empty_frac, null)) as hist_empty_rate_target_hour_daytype,
    avg(h.mean_bikes) as hist_mean_bikes_target_hour,
    count(h.hour_utc) as hist_target_hour_days
  from base b
  join hourly h
    on h.station_id = b.station_id and h.local_hour = b.target_local_hour
   and timestamp_add(h.hour_utc, interval 1 hour) <= b.prediction_at_utc
  group by 1
),
recent as (
  -- How empty the station has been over the 24 hours before the prediction.
  select b.prediction_id,
    avg(h.empty_frac) as recent_empty_rate_24h,
    min(h.mean_bikes) as recent_min_mean_bikes_24h
  from base b
  join hourly h
    on h.station_id = b.station_id
   and h.hour_utc >= timestamp_sub(b.prediction_at_utc, interval 24 hour)
   and timestamp_add(h.hour_utc, interval 1 hour) <= b.prediction_at_utc
  group by 1
)
select b.*,
  s.hist_empty_rate_target_hour,
  s.hist_empty_rate_target_hour_7d,
  s.hist_empty_rate_target_hour_daytype,
  s.hist_mean_bikes_target_hour,
  coalesce(s.hist_target_hour_days, 0) as hist_target_hour_days,
  r.recent_empty_rate_24h,
  r.recent_min_mean_bikes_24h
from base b
left join same_hour s using (prediction_id)
left join recent r using (prediction_id);

select split, count(*) as rows_, countif(no_bike = 1) as no_bike_rows, round(avg(no_bike), 4) as no_bike_rate,
  min(prediction_at_utc) as first_origin_utc, max(prediction_at_utc) as last_origin_utc,
  count(distinct station_id) as stations
from `${project}.${dataset}.split_h${horizon_minutes}`
group by split order by min(prediction_at_utc);
