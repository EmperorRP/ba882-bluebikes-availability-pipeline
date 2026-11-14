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
where split is not null;

select split, count(*) as rows_, countif(no_bike = 1) as no_bike_rows, round(avg(no_bike), 4) as no_bike_rate,
  min(prediction_at_utc) as first_origin_utc, max(prediction_at_utc) as last_origin_utc,
  count(distinct station_id) as stations
from `${project}.${dataset}.split_h${horizon_minutes}`
group by split order by min(prediction_at_utc);
