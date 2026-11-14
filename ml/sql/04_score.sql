-- Score val and test rows with every method so models and baselines are compared on identical rows.
-- score = estimated probability (or 0/1 rule) that the station has NO bike at the target time.
create or replace table `${project}.${dataset}.scores_h${horizon_minutes}` as
with eval_rows as (
  select * from `${project}.${dataset}.split_h${horizon_minutes}` where split in ('val', 'test')
),
station_hour_prior as (
  select station_id, target_local_hour, avg(no_bike) as p
  from `${project}.${dataset}.split_h${horizon_minutes}` where split = 'train' group by 1, 2
),
station_prior as (
  select station_id, avg(no_bike) as p
  from `${project}.${dataset}.split_h${horizon_minutes}` where split = 'train' group by 1
),
global_prior as (
  select avg(no_bike) as p from `${project}.${dataset}.split_h${horizon_minutes}` where split = 'train'
)
select 'persistence' as method, split, prediction_id, station_id, no_bike, cast(origin_no_bike as float64) as score
from eval_rows
union all
select 'station_hour_prior', e.split, e.prediction_id, e.station_id, e.no_bike, coalesce(sh.p, s.p, g.p)
from eval_rows e
left join station_hour_prior sh using (station_id, target_local_hour)
left join station_prior s using (station_id)
cross join global_prior g
union all
-- Rule: how often this station was empty at the target hour on earlier days (point-in-time, no training).
select 'station_history_rule', split, prediction_id, station_id, no_bike, coalesce(hist_empty_rate_target_hour, 0)
from eval_rows
-- One ML.PREDICT block per model listed in the `models` parameter (rendered by bqml.py).
${model_predictions};
