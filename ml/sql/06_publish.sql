-- Publish forecasts for the frontend: horizon ${horizon_minutes} min, model ${primary_model}.
-- Rows are the held-out test window (the last ${test_hours}h of origins), which the model never saw during
-- training or model selection, so the actual outcome is known for every forecast.
-- Scores are reused from scores_h${horizon_minutes} (04_score); no model is re-run here.
--   risk_rank  : 1 = most likely to have no bike among all stations forecast at the same time. Ties are broken
--                exactly as in 05_metrics, so the top-${top_k} here are the stations behind precision_at_k.
--   at_risk    : prob_no_bike >= the F1-maximising threshold chosen on val (metrics_h${horizon_minutes}).
assert (select count(*) from `${project}.${dataset}.metrics_h${horizon_minutes}`
        where method = '${primary_model}' and split = 'val' and threshold is not null) = 1
  as 'metrics_h${horizon_minutes} has no val threshold for ${primary_model}; run 04_score and 05_metrics first';

create or replace table `${project}.${dataset}.forecasts_h${horizon_minutes}`
options (description = 'Held-out ${horizon_minutes}-minute no-bike forecasts from ${primary_model}_h${horizon_minutes} for the frontend. See docs/ml/forecast-serving-contract.md')
as
with threshold as (
  select threshold from `${project}.${dataset}.metrics_h${horizon_minutes}`
  where method = '${primary_model}' and split = 'val'
),
f as (
  select s.prediction_id, s.station_id, round(s.score, 4) as score, s.no_bike,
    sp.prediction_at_utc, sp.target_at_utc,
    sp.origin_bikes_available, sp.origin_docks_available, sp.origin_capacity
  from `${project}.${dataset}.scores_h${horizon_minutes}` s
  join `${project}.${dataset}.split_h${horizon_minutes}` sp using (prediction_id)
  where s.method = '${primary_model}' and s.split = 'test'
)
select
  ${horizon_minutes} as horizon_minutes,
  '${primary_model}' as model,
  f.prediction_id,
  f.station_id,
  d.station_name,
  d.latitude,
  d.longitude,
  f.prediction_at_utc as forecast_made_at_utc,
  f.target_at_utc as forecast_for_utc,
  datetime(f.prediction_at_utc, 'America/New_York') as forecast_made_at_local,
  datetime(f.target_at_utc, 'America/New_York') as forecast_for_local,
  f.origin_bikes_available as bikes_available_at_forecast,
  f.origin_docks_available as docks_available_at_forecast,
  f.origin_capacity as capacity,
  f.score as prob_no_bike,
  round(1 - f.score, 4) as prob_has_bike,
  row_number() over (partition by f.prediction_at_utc
                     order by f.score desc, farm_fingerprint(cast(f.prediction_id as string))) as risk_rank,
  f.score >= t.threshold as at_risk,
  t.threshold as at_risk_threshold,
  1 - f.no_bike as actual_has_bike,
  f.prediction_at_utc = max(f.prediction_at_utc) over () as is_latest_forecast,
  current_timestamp() as published_at_utc
from f
cross join threshold t
left join `${project}.marts.dim_station` d on d.station_id = f.station_id;

assert (select count(*) from `${project}.${dataset}.forecasts_h${horizon_minutes}`) > 0
  as 'forecasts_h${horizon_minutes} is empty';

select horizon_minutes, model, count(*) as rows_, count(distinct station_id) as stations,
  countif(station_name is null) as rows_missing_station_metadata,
  min(forecast_made_at_local) as first_forecast_local, max(forecast_made_at_local) as last_forecast_local,
  round(avg(prob_no_bike), 4) as mean_prob_no_bike, round(1 - avg(actual_has_bike), 4) as actual_no_bike_rate,
  countif(at_risk) as at_risk_rows, any_value(at_risk_threshold) as at_risk_threshold
from `${project}.${dataset}.forecasts_h${horizon_minutes}`
group by 1, 2;
