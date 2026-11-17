# Forecast serving contract (frontend ↔ ML)

This page is for the frontend team. It describes the BigQuery table the app reads its bike-availability forecasts from: what each row means, which time windows exist, and the queries behind the main screens.

Published 2026-11-17 from the models in [ml/README.md](../../ml/README.md).

## In one paragraph

For each station, the model gives the chance that it will have **no bike** 1, 3, 6 or 24 hours later. Collection stopped on Nov 9, so there are no live forecasts. The table instead holds the **held-out test window**: the last 36 hours of data, which the model never saw during training or tuning. Every forecast has a known outcome (`actual_has_bike`), so the app can replay the forecasts and also show whether each one was right. Present it as **"demo data: Nov 7–9, 2026"**, not as live availability.

## Where it lives

| | |
|---|---|
| View to read | `ba882-bluebikes-pipeline.ml_models.station_forecasts` (all horizons) |
| Underlying tables | `ml_models.forecasts_h60`, `forecasts_h180`, `forecasts_h360`, `forecasts_h1440` (same columns) |
| Location | BigQuery `US` |
| Size | 1,045,539 rows (about 260K per horizon, about 605 stations per forecast time) |
| Access | Readers need `roles/bigquery.dataViewer` on `ml_models` and `roles/bigquery.jobUser` on the project |
| Refreshed by | `bluebikes_ml_training_dag` (`publish` tasks), only after a horizon's model passes its quality gate |

**Grain:** one row per station × forecast time × horizon. `prediction_id` is unique across the whole view. So is (`horizon_minutes`, `station_id`, `forecast_made_at_utc`).

## Columns

| Column | Type | Meaning |
|---|---|---|
| `horizon_minutes` | INT64 | 60, 180, 360 or 1440. How far ahead the forecast looks. |
| `model` | STRING | `logreg` for 1/3/6 h, `boosted` for 24 h (the best model per horizon). |
| `prediction_id` | STRING | Unique row key. |
| `station_id` | STRING | GBFS station ID (same as `marts.dim_station`). |
| `station_name` | STRING | Station name. Present on every row. |
| `latitude`, `longitude` | FLOAT64 | Station location for the map. Present on every row. |
| `forecast_made_at_utc` | TIMESTAMP | When the forecast was made (the "now" of the forecast). All stations in one snapshot share this exact value. |
| `forecast_for_utc` | TIMESTAMP | The time being forecast: `forecast_made_at_utc` + horizon. |
| `forecast_made_at_local`, `forecast_for_local` | DATETIME | The same two times in Boston time (America/New_York). Use these for display. |
| `bikes_available_at_forecast` | INT64 | Bikes at the station when the forecast was made. |
| `docks_available_at_forecast` | INT64 | Empty docks at that time. |
| `capacity` | INT64 | Station capacity. |
| `prob_no_bike` | FLOAT64 | Model's chance (0–1) that the station has **zero** bikes at `forecast_for_utc`. |
| `prob_has_bike` | FLOAT64 | `1 - prob_no_bike`. The number to show riders ("82% chance of a bike"). |
| `risk_rank` | INT64 | 1 = the station most likely to be empty among all stations forecast at the same time and horizon. |
| `at_risk` | BOOL | `prob_no_bike >= at_risk_threshold`. A yes/no flag for colouring the map. |
| `at_risk_threshold` | FLOAT64 | The cut-off for that horizon, chosen on validation data. It differs by horizon. |
| `actual_has_bike` | INT64 | What really happened: 1 = at least one bike, 0 = empty. Only exists because this is historical data. |
| `is_latest_forecast` | BOOL | True for the last forecast time in that horizon (about 600 rows per horizon). |
| `published_at_utc` | TIMESTAMP | When the table was published. Show as "data as of". |

## Time windows

Forecast times are snapshot timestamps roughly every 5 minutes (for example 10:50:12 or 10:55:09), not exact round times. Each horizon covers 432–433 forecast times.

| Horizon | Forecast made (Boston) | Forecast for (Boston) |
|---|---|---|
| 1 h | Nov 8 05:50 → Nov 9 17:50 | Nov 8 06:50 → Nov 9 18:50 |
| 3 h | Nov 8 03:50 → Nov 9 15:50 | Nov 8 06:50 → Nov 9 18:50 |
| 6 h | Nov 8 00:50 → Nov 9 12:50 | Nov 8 06:50 → Nov 9 18:50 |
| 24 h | Nov 7 06:55 → Nov 8 18:50 | Nov 8 06:55 → Nov 9 18:50 |

This gives two useful demo modes:

- **"Plan a trip" (pick a "now", see 1/3/6/24 h ahead):** all four horizons share forecast-made times only between **Nov 8 05:50 and Nov 8 18:50** Boston time. Use a "now" inside that range, or hide horizons that have no forecast at the chosen time.
- **"How will 6 pm look?" (pick a target time, compare horizons):** all four horizons forecast the same 36 h of target times, **Nov 8 06:50 → Nov 9 18:50**.

Snapshot seconds differ slightly between horizons, so match times on 5-minute buckets, not exact equality:

```sql
timestamp_seconds(div(unix_seconds(forecast_made_at_utc), 300) * 300) as made_bucket_utc
```

## Queries for the main screens

**Station map at a chosen "now", one horizon.** Replace the time with the slider value, in UTC (Boston + 5 h in November):

```sql
select station_id, station_name, latitude, longitude, bikes_available_at_forecast,
       forecast_for_local, prob_has_bike, at_risk, risk_rank
from `ba882-bluebikes-pipeline.ml_models.station_forecasts`
where horizon_minutes = 1440
  and timestamp_seconds(div(unix_seconds(forecast_made_at_utc), 300) * 300) = timestamp '2026-11-08 17:00:00 UTC';
```

**Default view (no slider):** use `where horizon_minutes = 1440 and is_latest_forecast`. Every horizon's latest forecast targets Nov 9 ≈ 18:50 Boston time.

**"Most likely to be empty" list:** add `and risk_rank <= 50 order by risk_rank` to the map query. On the test data, about 24% of the 24 h top-50 really were empty, against 15% for a "no bike now" rule. At 1 h the figure is 41%.

**One station, every horizon, at a chosen "now"** (the "plan a trip" card):

```sql
select horizon_minutes, forecast_for_local, prob_has_bike, at_risk
from `ba882-bluebikes-pipeline.ml_models.station_forecasts`
where station_id = @station_id
  and timestamp_seconds(div(unix_seconds(forecast_made_at_utc), 300) * 300) = @now_bucket_utc
order by horizon_minutes;
```

**Forecast vs. reality for one station** (a line chart over the window):

```sql
select forecast_for_local, prob_has_bike, actual_has_bike
from `ba882-bluebikes-pipeline.ml_models.station_forecasts`
where station_id = @station_id and horizon_minutes = 1440
order by forecast_for_utc;
```

**Station list / search:** `select distinct station_id, station_name, latitude, longitude from ...station_forecasts`. For metadata beyond that, use `marts.dim_station`.

## How to present the numbers

- **Show `prob_has_bike` as a percentage** (rounded, for example "94% chance of a bike"). Most stations are above 90%. Only about 5% of station-times are really empty.
- **Use `at_risk` for map colour**, not a fixed probability cut-off. The threshold differs by horizon (0.28 at 1 h, 0.24 at 3 h, 0.23 at 6 h, 0.36 at 24 h), and the flag already accounts for that.
- **Warnings get less reliable further ahead.** Of stations flagged `at_risk`, the share that were really empty is 62% at 1 h, 46% at 3 h, 38% at 6 h and 32% at 24 h. The flag catches 62% of empty stations at 1 h but only 13% at 24 h. A label such as "risk of no bikes" is fair. "Will be empty" is not.
- **At 24 h, prefer the ranking to the exact percentage.** The 24 h model's average probability (6.1%) is a little above the true empty rate (5.0%). Its ordering is good, but the exact numbers are rough.
- **Show `actual_has_bike` only in a clearly labelled "how did we do?" or replay mode.** A real app would not know it.
- **Always show the data window** ("Demo data: forecasts for Nov 8–9, 2026") and `published_at_utc`.

Model quality for an "About the model" panel, test window, no-bike class (from `ml_models.metrics_h{60,180,360,1440}`):

| Horizon | Model | Avg. precision | Persistence baseline | Random |
|---|---|---|---|---|
| 1 h | logreg | 0.590 | 0.404 | 0.05 |
| 3 h | logreg | 0.376 | 0.215 | 0.05 |
| 6 h | logreg | 0.259 | 0.128 | 0.05 |
| 24 h | boosted | 0.230 | 0.095 | 0.05 |

## Cost and loading tips

- The data is fixed until collection resumes, so the simplest approach is to **export once** and bundle the file with the app. One horizon is about 260K rows. For example: `bq query --use_legacy_sql=false --format=csv --max_rows=300000 'select ... where horizon_minutes = 1440' > forecasts_24h.csv`. Alternatively, load it once at app start and cache it.
- If the app queries BigQuery live, always filter on `horizon_minutes` and a time. The tables are not partitioned, so each query scans every row of the columns it selects: about 70 MB for all columns of one horizon table, or about 27 MB for the columns a map needs. That's cheap, but cache results rather than querying on every interaction.
- Read the view, not the `forecasts_h*` tables, so new horizons or republishes need no app change.

## Stability and change process

- Column names and meanings above are a contract. Changes go through a PR that updates this page. Columns may be added; existing ones will not be renamed or removed without notice.
- When the DAG retrains on new data, the tables are replaced, and the time windows move to the newest 36 h. Read the windows from the data (`min`/`max` of the time columns, or `is_latest_forecast`) instead of hard-coding the dates above.
- A horizon is republished only when its model beats the persistence baseline on held-out data. If a gate fails, the previous forecasts stay in place.
- **Not provided:** live forecasts for the current time, dock forecasts, and e-bike vs. classic split. Live forecasting would need snapshot collection to resume, plus a step that scores the newest snapshot instead of the test window.
