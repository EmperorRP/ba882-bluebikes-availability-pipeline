-- Main candidate: gradient-boosted trees (XGBoost inside BigQuery ML).
-- Early stopping uses the val rows. station_id is deliberately excluded: run 2 target-encoded it and
-- over-fit after 14 iterations (probabilities ~3x too low); the station history features describe each
-- station point-in-time instead.
-- Cost control: trains on every ${boosted_origin_step}th five-minute origin slot only (scoring still uses all rows).
-- The first full-data run (32 iterations) billed 45 GB.
create or replace model `${project}.${dataset}.boosted_h${horizon_minutes}`
options (
  model_type = 'BOOSTED_TREE_CLASSIFIER',
  input_label_cols = ['no_bike'],
  data_split_method = 'CUSTOM',
  data_split_col = 'is_eval',
  tree_method = 'HIST',
  -- Run 1 (learn_rate 0.1, min_rel_progress 0.001) stopped at iteration 32 while still improving,
  -- leaving probabilities far too low. A larger step reaches a good fit in fewer (billed) iterations.
  max_iterations = 80,
  learn_rate = 0.3,
  max_tree_depth = 6,
  subsample = 0.8,
  colsample_bytree = 0.8,
  l2_reg = 1.0,
  early_stop = true,
  min_rel_progress = 0.0002,
  enable_global_explain = true
) as
select
  no_bike,
  split = 'val' as is_eval,
  target_local_hour,
  target_local_day_of_week,
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
where split in ('train', 'val')
  and mod(div(extract(minute from prediction_at_utc), 5), ${boosted_origin_step}) = 0;
