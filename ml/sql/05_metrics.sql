-- Metrics for the no-bike class.
--   average_precision : area under the precision-recall curve (threshold-free; main ranking metric)
--   threshold         : the cut-off that maximises F1 on VAL, then applied unchanged to TEST
--   brier             : mean squared error of the probability (calibration + sharpness; lower is better)
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
  round(t.m.f1, 3) as f1
from summary
join ap using (method, split)
left join at_threshold t using (method, split);

select * except (horizon_minutes, evaluated_at_utc)
from `${project}.${dataset}.metrics_h${horizon_minutes}`
order by split desc, average_precision desc;
