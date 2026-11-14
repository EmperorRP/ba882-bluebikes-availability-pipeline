-- Interpretable candidate: L2 logistic regression. Hour, weekday and station are one-hot encoded.
-- Val rows are passed as the evaluation split (is_eval); test rows are never seen here.
create or replace model `${project}.${dataset}.logreg_h${horizon_minutes}`
options (
  model_type = 'LOGISTIC_REG',
  input_label_cols = ['no_bike'],
  data_split_method = 'CUSTOM',
  data_split_col = 'is_eval',
  l2_reg = 1.0,
  max_iterations = 50,
  -- Default (0.01) stopped after 5 iterations while eval loss was still falling.
  min_rel_progress = 0.001,
  enable_global_explain = true
) as
select
  no_bike,
  split = 'val' as is_eval,
  station_id,
  target_hour_cat,
  target_dow_cat,
  target_is_weekend,
  origin_bikes_available,
  origin_no_bike,
  origin_docks_available,
  origin_capacity,
  origin_bike_fill_ratio,
  origin_report_age_seconds,
  bikes_available_lag,
  bikes_change_lag,
  has_lag_inventory,
  observed_departures_matching_hour_lookback,
  observed_arrivals_matching_hour_lookback,
  net_inflow_per_day_lookback,
  has_trip_history,
  forecast_temperature_c,
  forecast_humidity_pct,
  forecast_precipitation_mm,
  forecast_wind_speed_kmh,
  hist_empty_rate_target_hour,
  hist_empty_rate_target_hour_7d,
  hist_empty_rate_target_hour_daytype,
  hist_mean_bikes_target_hour,
  hist_target_hour_days,
  recent_empty_rate_24h,
  recent_min_mean_bikes_24h
from `${project}.${dataset}.split_h${horizon_minutes}`
where split in ('train', 'val');
