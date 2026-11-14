# Machine learning

ML-01 defines the target and forecast horizon, compares persistence/seasonal baselines with a candidate model, uses chronological evaluation, and versions training inputs and artifacts. Deploy the selected model and define weekly retraining and rollback criteria.

## Scope (2026-11-07, data window updated 2026-11-13)

- **Target:** `target_has_bike`, meaning the station has at least one bike of any type available at the target time. Docks are not predicted. Models predict the complement, `no_bike = 1 - target_has_bike`, because the no-bike case is the one riders care about.
- **Horizons:** **24 hours (1440 minutes) is the primary horizon.** 1, 3 and 6 hours (60, 180 and 360 minutes) are secondary.
- **Data window:** continuous five-minute snapshots from 2026-10-29 10:24 to 2026-11-09 18:55 America/New_York. Collection has ended. There is one gap on Nov 2 from 09:30 to 18:52 local. The marts were fully rebuilt on 2026-11-14 01:28 UTC, so 24 h origins run through Nov 8 18:50 local (1.70M rows).
- **Input:** `ml.station_availability_training_ready`. The no-bike share is about 6.5% and varies by day (4–9%).
- **Evaluation:** chronological split with an embargo of at least the horizon plus the 15-minute label window between train and test (just over 24 h for the primary horizon). Rows from the same collection are not independent samples.

## Approach: compute on BigQuery, orchestrate with Airflow

Training, scoring and evaluation all run inside BigQuery as SQL (BigQuery ML). No data leaves the warehouse. Airflow only runs the SQL steps in order. Outputs go to the `ml_models` dataset, which is separate from the dbt-managed `ml` dataset, so dbt rebuilds never touch models.

| Step | File | Output in `ml_models` |
|---|---|---|
| 1. Chronological split | `sql/01_split.sql` | `split_h{H}`: rows labelled `train` / `val` / `test` |
| 2. Logistic regression | `sql/02_train_logreg.sql` | model `logreg_h{H}` |
| 3. Boosted trees (XGBoost) | `sql/03_train_boosted.sql` | model `boosted_h{H}` |
| 4. Score models + baselines | `sql/04_score.sql` | `scores_h{H}` |
| 5. Metrics | `sql/05_metrics.sql` | `metrics_h{H}` |

`{H}` is the horizon in minutes. The split is data-driven:
- **test:** the last `test_hours` (36) of origins
- **val:** `val_hours` (24) of origins ending one embargo before test
- **train:** everything whose labels close one embargo before val

Model choices and the decision threshold are made on **val**. **Test** is only used for the final report.

Baselines:
- **persistence:** no bike now → no bike at the target time. At 24 h this is the same as "same time yesterday".
- **station_hour_prior:** the station's no-bike rate at that hour of day, computed on train only.

Metrics are for the no-bike class:
- **average precision** (area under the precision–recall curve): the main ranking metric
- **F1 / precision / recall** at the threshold that maximises F1 on val, applied unchanged to test
- **Brier score:** how accurate the probabilities are

Accuracy is not reported, because always predicting "has a bike" already scores about 95%.

### Running manually

`ml/bqml.py` fills the template parameters and prints SQL. Pass the SQL to `bq` on stdin, because `bq` treats a query that starts with `--` as a flag:

```bash
python ml/bqml.py 01_split --horizon-minutes 1440 | bq query --use_legacy_sql=false
```

Run steps 01 → 05 in order. Any parameter in `DEFAULTS` can be overridden, for example `--horizon-minutes 60` for the 1 h model.

## Results (2026-11-13, test = last 36 h of origins, ~260K rows, 4.9% no-bike)

Avg. precision is the area under the precision–recall curve for the no-bike class; random guessing scores 0.05. Top-50 precision: at each prediction time, the share of the 50 stations ranked most at risk that really had no bike. The best possible top-50 precision is about 0.57, because some prediction times have fewer than 50 empty stations.

| Horizon | Best model | Avg. precision | Top-50 precision | Persistence AP | Persistence top-50 |
|---|---|---|---|---|---|
| 1 h | logreg | 0.590 | 0.411 | 0.404 | 0.357 |
| 3 h | logreg | 0.376 | 0.316 | 0.215 | 0.257 |
| 6 h | logreg | 0.259 | 0.264 | 0.128 | 0.189 |
| **24 h** | **boosted** | **0.230** | **0.241** | 0.095 | 0.149 |

24 h model history (test average precision):
- logreg: 0.139
- \+ station history features: 0.158
- boosted tree, station_id target-encoded: 0.149 (over-fit and badly calibrated)
- boosted tree, history features, no station_id: **0.230**

The station history features are the largest single improvement. Validation-day scores are lower than test scores (for example, 24 h boosted scores 0.147 on val), so day-to-day variance is large with about 10 days of data.

Cost: each 24 h boosted-tree run bills about 14 GB (on 15-minute-thinned origins). Logistic regression bills about 0.2 GB.
