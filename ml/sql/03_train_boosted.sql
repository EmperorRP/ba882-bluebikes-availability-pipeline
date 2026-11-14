-- Main candidate: gradient-boosted trees (XGBoost inside BigQuery ML).
-- station_id is target-encoded (fit on training rows only). Early stopping uses the val rows.
create or replace model `${project}.${dataset}.boosted_h${horizon_minutes}`
options (
  model_type = 'BOOSTED_TREE_CLASSIFIER',
  input_label_cols = ['no_bike'],
  data_split_method = 'CUSTOM',
  data_split_col = 'is_eval',
  category_encoding_method = 'TARGET_ENCODING',
  tree_method = 'HIST',
  max_iterations = 300,
  learn_rate = 0.1,
  max_tree_depth = 6,
  subsample = 0.8,
  colsample_bytree = 0.8,
  l2_reg = 1.0,
  early_stop = true,
  min_rel_progress = 0.001,
  enable_global_explain = true
) as
select
  no_bike,
  split = 'val' as is_eval,
  station_id,
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
  forecast_wind_speed_kmh
from `${project}.${dataset}.split_h${horizon_minutes}`
where split in ('train', 'val');
