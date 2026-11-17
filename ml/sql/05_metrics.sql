-- Metrics for the no-bike class.
--   average_precision : area under the precision-recall curve (threshold-free; main ranking metric)
--   threshold         : the cut-off that maximises F1 on VAL, then applied unchanged to TEST
--   brier             : mean squared error of the probability (calibration + sharpness; lower is better)
--   precision_at_k    : at each prediction time, of the ${top_k} stations ranked most at risk, the share that
--                       really had no bike (averaged over prediction times). best_possible_at_k is the
--                       ceiling, since some times have fewer than ${top_k} empty stations.
--   recall_at_k       : share of all no-bike cases that landed in those top-${top_k} lists
create or replace table `${project}.${dataset}.metrics_h${horizon_minutes}` as
with s as (
  select method, split, round(score, 4) as score, no_bike from `${project}.${dataset}.scores_h${horizon_minutes}`
),
per_score as (
  select method, split, score, sum(no_bike) as pos_at, count(*) - sum(no_bike) as neg_at
  from s group by 1, 2, 3
),
curve as (
  select *,
    sum(pos_at) over w as tp,
    sum(neg_at) over w as fp,
    sum(pos_at) over p as total_pos
  from per_score
  window p as (partition by method, split),
         w as (partition by method, split order by score desc rows unbounded preceding)
),
points as (
  select *,
    safe_divide(tp, tp + fp) as precision_,
    safe_divide(tp, total_pos) as recall,
    safe_divide(2 * tp, 2 * tp + fp + (total_pos - tp)) as f1,
    safe_divide(tp, total_pos)
      - coalesce(lag(safe_divide(tp, total_pos)) over (partition by method, split order by score desc), 0) as recall_step
  from curve
),
ap as (
  select method, split, sum(recall_step * precision_) as average_precision from points group by 1, 2
),
val_threshold as (
  select method, array_agg(score order by f1 desc, score desc limit 1)[offset(0)] as threshold
  from points where split = 'val' group by method
),
at_threshold as (
  select p.method, p.split, v.threshold,
    array_agg(struct(p.precision_, p.recall, p.f1) order by p.score asc limit 1)[offset(0)] as m
  from points p join val_threshold v using (method)
  where p.score >= v.threshold
  group by 1, 2, 3
),
ranked as (
  select s.method, s.split, s.no_bike, sp.prediction_at_utc,
    row_number() over (partition by s.method, s.split, sp.prediction_at_utc
                       order by s.score desc, farm_fingerprint(cast(s.prediction_id as string))) as rk
  from `${project}.${dataset}.scores_h${horizon_minutes}` s
  join `${project}.${dataset}.split_h${horizon_minutes}` sp using (prediction_id)
),
per_time as (
  select method, split, prediction_at_utc,
    countif(rk <= ${top_k} and no_bike = 1) as hits,
    countif(rk <= ${top_k}) as k_actual,
    sum(no_bike) as empties
  from ranked group by 1, 2, 3
),
top_k as (
  select method, split,
    avg(safe_divide(hits, k_actual)) as precision_at_k,
    avg(safe_divide(least(empties, k_actual), k_actual)) as best_possible_at_k,
    safe_divide(sum(hits), sum(empties)) as recall_at_k
  from per_time group by 1, 2
),
summary as (
  select method, split, count(*) as rows_, avg(no_bike) as no_bike_rate,
    avg(pow(score - no_bike, 2)) as brier
  from `${project}.${dataset}.scores_h${horizon_minutes}` group by 1, 2
)
select
  ${horizon_minutes} as horizon_minutes,
  current_timestamp() as evaluated_at_utc,
  method, split, rows_,
  round(no_bike_rate, 4) as no_bike_rate,
  round(ap.average_precision, 4) as average_precision,
  round(brier, 4) as brier,
  t.threshold,
  round(t.m.precision_, 3) as precision_,
  round(t.m.recall, 3) as recall,
  round(t.m.f1, 3) as f1,
  ${top_k} as top_k,
  round(k.precision_at_k, 3) as precision_at_k,
  round(k.best_possible_at_k, 3) as best_possible_at_k,
  round(k.recall_at_k, 3) as recall_at_k
from summary
join ap using (method, split)
join top_k k using (method, split)
left join at_threshold t using (method, split);

select * except (horizon_minutes, evaluated_at_utc)
from `${project}.${dataset}.metrics_h${horizon_minutes}`
order by split desc, average_precision desc;
