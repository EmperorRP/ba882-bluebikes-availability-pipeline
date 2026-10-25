# Availability features and labels at a prediction origin

## Purpose and published objects

This increment creates a reproducible availability-data contract, not a trained forecaster. The primary target is whether at least one rentable bike is observed near a requested future time. It follows the project's up-to-24-hour product question, with configurable initial settings for ML review.

- intermediate.int_availability_prediction_requests (view): one observed station collection origin x configured horizon. Every inventory observation remains represented, including unusable origins; no dense inventory grid is fabricated.
- marts.mart_station_availability_features (table): one prediction_id with inventory, calendar, optional lag, original-trip-code history and versioned forecast weather. Source availability lineage is retained for auditing.
- ml.mart_station_availability_labels (table): one prediction_id with nullable primary outcome and separately stored future-observation provenance.
- ml.station_availability_training_ready (view): usable-origin rows with a real non-null target, explicit predictors, target and evaluation keys. An empty view is an honest result of missing outcome coverage.
- ml.availability_sample_coverage (view): requests, feature availability, actual labels and eligible rows by horizon.

All datasets are US. The two new tables are partitioned by UTC prediction date and clustered by station_id / horizon_minutes. Schema resolution now includes ml in the same scoped shared-schema rule used for intermediate and marts. Existing source/staging/history/flow relations are not rewritten by this selected build.

## Initial policy

The following dbt variables are initial engineering defaults, not a final ML-01/product agreement:

- availability_horizons_minutes: [60, 180, 360, 1440] (1, 3, 6, 24 hours).
- availability_label_tolerance_minutes: 15, after the target instant only, inclusive at both ends.
- availability_max_report_age_minutes: 60; it can tighten, but cannot relax the inventory history's existing strict eligibility.
- availability_lag_minutes: 60.
- availability_trip_lookback_days: 56.

The policy macro rejects empty/duplicate horizons, horizons outside 1-1440 integer minutes and non-positive/non-integer other settings. The feature table records lag_minutes and trip_lookback_days. Changing these settings requires rebuilding the dependent models and preserving a new version for a real experiment.

prediction_at_utc is the actual warehouse status collection/ingestion time, not an arbitrary historical app request or station report time. target_at_utc is prediction_at_utc + horizon. New York target calendar fields are derived from that instant. An earlier prediction cannot consume a later-ingested source even if its event date is historical.

## Feature availability rules

Origin inventory uses the observation already collected at the origin and its known-at-collection metadata. Unusable origin bike/dock/capacity/ratio values are masked to null; is_origin_usable is false and the row cannot enter training. All audit fields are not intended as automatic model predictors.

Lag inventory first chooses the latest station collection available at or before origin minus the configured lag, without skipping a bad latest row to hunt for a good older one. The report must also be within the report-age limit at that lag cutoff and satisfy strict history usability. Otherwise bikes_available_lag is null and has_lag_inventory is false. This is a bounded as-of observation, not interpolation or a promise that the station was observed exactly one hour earlier.

Trip features match the original trip code known at the origin to the endpoint intermediate's original trip_station_id; they do not use its canonical station ID or a future latest bridge. They sum observed departures/arrivals whose local hour and weekday match the requested target, within the lookback before the origin. Only complete event hours ending by the origin and groups whose latest contributing ingestion is no later than the origin are admitted. No matching events produces null count features and a zero observed-date diagnostic, rather than an assertion of zero demand.

Trip event times inherit the explicitly inferred America/New_York interpretation in [the trip/weather contract](trip-weather-model-contract.md). These are observed raw-code event profiles, not average daily demand or historical availability probabilities. Missing periods and zero-event days have not been independently validated; historical code reuse/location changes are not ruled out. Group-level latest-ingestion gating is conservative: partially available groups are withheld rather than reconstructed record by record. The current inputs are latest rebuilt history. Revisions to old raw rides or mappings require versioned source reconstruction for an exact historical backtest; the timestamp gates alone do not make the entire warehouse bitemporal.

Forecast weather must be forecast_api with complete availability lineage, future-at-availability status, target UTC weather hour and availability no later than the prediction origin. Choose the latest eligible available version, then fetch timestamp/record-ID tie breaks. Historical reanalysis and 336 legacy unversioned forecast rows cannot fill future forecast features. Missing forecast versions produce null numeric fields and has_forecast_weather=false. Fetch time is not provider issuance time. Weather is the forecast for the containing UTC hour; it is not interpolated to the fractional-minute target.

## Primary label rule

Join the same station's strict usable bike observations whose SOURCE reported_at_utc is in [target, target + 15 minutes] under the configured tolerance. A later collection carrying a report from before the target is not a label. Collection availability must be at/after the target and no more than the configured report-age limit after the report.

Choose the earliest qualifying source report, then its earliest collection, then observation ID. The outcome is target_has_bike = 1 if that observation has at least one rentable bike, otherwise 0. Missing candidates yield null target/outcome/provenance and no_usable_label_in_window. This is an observation within the stated window, not proof of inventory at the exact target instant, nor whether a bike was available throughout the interval. Repeated collections of the same report are not additional independent labels.

Labels necessarily use a future outcome; their timestamps, counts and IDs are kept out of the feature model. The training-ready view contains target_has_bike as the designated target, with an explicit predictor allowlist and evaluation keys only. Dock prediction is not separately labelled/trained in this increment.

## Validation and synthetic cases

With upstream staging, dimensions, endpoint history and inventory history already built:

    dbt parse
    dbt build --select tag:point_in_time_ml

Data tests verify keys, origin/horizon coverage, preserved requests, availability boundaries, latest eligible forecast selection, null outcomes, label window/binary values and training/coverage membership. A separate warning reports horizons with zero eligible labels. Passing these tests is not a statement of forecasting quality or statistical sample adequacy.

The dbt unit test availability_labels_window_and_quality mocks both label-model inputs in temporary test queries. It proves positive and negative cases: valid future report, stale pre-target report collected later, out-of-window report, unusable observation, missing station and the inclusive upper boundary with a true zero-bike outcome. Repeated reports choose the first availability. Synthetic fixtures are isolated from the real warehouse input and published feature/label tables.

The verification JSON records policy, relation sizes, source availability, feature coverage, test results, code fingerprints and ancestry checks. Prior layer tests are not rerun by this selected build. Source freshness remains separate and unchanged.

## ML handoff and limits

The initial real inventory consists of six irregular collections. The coverage audit must be consulted before model fitting; a large feature-row count is not a labelled sample count. No labels are fabricated, no model is trained and no accuracy metrics or production forecasts are claimed.

Danish should review horizon/tolerance/freshness choices, predictor selection, missing-feature policy and the true target versus a separately named demand/shortage proxy. Use chronological evaluation with source-report groups and a horizon/label-window embargo to prevent overlapping observations crossing splits. Preserve the input/config/code version for each experiment. IDs, raw timestamps and provenance are evaluation/audit keys, not a blanket SELECT * predictor list. Continuous GBFS collection and sufficient labelled history are prerequisites for a defensible availability backtest. Arbitrary live request serving and production deployment remain separate work.

## Verified on 2026-10-21

- intermediate.int_availability_prediction_requests: 15,048 rows (VIEW).
- marts.mart_station_availability_features: 15,048 rows (TABLE).
- ml.mart_station_availability_labels: 15,048 rows (TABLE).
- ml.station_availability_training_ready: 0 rows (VIEW).
- ml.availability_sample_coverage: 4 rows (VIEW).

Policy: 1/3/6/24-hour horizons; 15-minute post-target observation tolerance. Every horizon has 3,762 requests and 3,712 strict usable origins, but ZERO observed outcomes and ZERO training-eligible rows. All 15,048 label records retain null outcomes; no model was trained.

| Horizon (hours) | Requests | Trip-code history | Forecast weather | Eligible labels |
| --- | ---: | ---: | ---: | ---: |
| 1 | 3762 | 1064 | 1254 | 0 |
| 3 | 3762 | 792 | 1254 | 0 |
| 6 | 3762 | 308 | 1254 | 0 |
| 24 | 3762 | 1112 | 1254 | 0 |

No request has a usable 60-minute inventory lag. The first four collection origins precede the trip-group and versioned-forecast ingestion, so their 10,032 requests have neither source as a feature. The final two origins have 5,016 forecast-feature rows and 3,276 observed trip-code profile rows in total. These counts include requests with unusable origin inventory; they are NOT labelled training samples.

Validation: parse passed; selected build created 2 tables and 3 views; 29 data tests ran (28 pass, 1 warning containing 4 horizons), plus 1 passing unit test. No failures/errors/skips. The independent audit found 0 future origin metadata, 0 future forecast versions, 0 future trip groups and 0 future inventory lags. Feature ancestry excludes the label model; future label provenance is absent from the training predictor view. The synthetic positive/boundary/negative label cases passed while the real label outcome columns remain null.

See [verification evidence](../evidence/availability-ml-verification-2026-10-21.json) for policy, code hashes, source times, exact model/test results and per-origin counts. No commit, push, PR, training, score or serving deployment was performed.
