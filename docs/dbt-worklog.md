# Marcus dbt work log

## 2026-10-21 - foundation (DBT-01)

1. Cloned main into Cloud Shell; base commit 88debb3 includes ingestion PR #13.
2. Inspected raw data read-only and recorded the audit in raw-data-audit-2026-10-21.md.
3. Checked ancestor/repository AGENTS.md files; none found. Repository working tree was clean before initialization.
4. Created feature/marcus-dbt-foundation. Installed dbt in ~/.venvs/ba882-bluebikes-dbt, separate from other course environments.
5. Added project/profile example and documented all four live raw sources and initial freshness expectations. Profile uses existing OAuth/ADC and US location.
6. Stored the active profile under ~/.dbt/ba882-bluebikes, outside the repository. No new credentials or IAM changes.

No transformation model, table creation, scheduled job, commit, push or PR is part of this increment.

## Foundation validation

- dbt Core 1.12.6; dbt-bigquery 1.12.1; direct dependencies pinned in dbt/requirements.txt.
- dbt debug: PASS, existing OAuth/ADC connects to ba882-bluebikes-pipeline, US.
- dbt parse: PASS. Manifest contains 4 sources and 0 executable nodes.
- dbt ls --resource-type source --output name: PASS; all four expected sources recognized.
- dbt source freshness: executed successfully but exits 1 because station_status is stale. station_information passes; weather_hourly warns. These are source-age signals, not connection or parsing failures.
- No dbt run/build/seed/snapshot commands executed. No warehouse objects created or changed.
- Active profile is outside the repo; generated target/logs and local profiles are ignored.
- Git diff whitespace check: result printed in terminal; no commit or push performed.

## 2026-10-21 - station staging and mapping

- Preflight: staging dataset was empty; 627 one-to-one station ID/code pairs, no ambiguous or changed mappings. Three trip codes remain unmapped at both endpoints.
- Created stg_station_information, stg_station_status and bridge_station_ids as US staging views; no raw data changes.
- Implemented UTC/local display times, snapshot deduplication, operational booleans, report-time quality and a nullable observed-availability flag.
- Added 16 generic contract tests and six singular SQL tests.
- dbt parse: PASS. dbt build --select tag:station_foundation: exit 0, 3 models succeeded, 20 tests passed, 2 warned, 0 errors or skips.
- Warnings: 24 suspect report records; 8 endpoint/code groups with missing/unmapped trip station IDs. Records are retained and warnings documented.
- Live queries verified 3,135 metadata records, 3,762 status records, 627 mapping rows, and Brighton Center mapping D32028.
- Published station-model-contract.md and updated README. Source freshness and ingestion continuity remain unresolved as documented in the audit.
- No commit/push, scheduling, trip/weather model or ML changes in this step.

## 2026-10-21 - trip and weather staging

- Read the existing March GCS archive and matched five original CSV ride timestamps to BigQuery; the CSV has no offset and its clock values were loaded as UTC.
- Inspected March 7/8/9 original-file hours: the spring-forward date has no 02:00-hour starts while neighboring dates have 50 and 17. America/New_York remains a documented inference.
- Inspected original weather JSON timezone and units (GMT, offset 0, Unix seconds; C / percent / mm / kmh).
- Added stg_trips and stg_weather views, source_timezone parameter, station mapping statuses and forecast version/availability flags. All original rows are retained.
- dbt parse passed; targeted build exited 0: 2 view models, 30 tests (29 pass, 1 warning, 0 errors/skips). The warning reports 336 legacy forecasts without timing metadata.
- Verified 3,527,328 unique rides, zero suspect converted times, 34 DST-adjusted durations; weather roles are 6,864 historical, 333 future-at-fetch, 339 past/current-at-fetch and 336 unversioned.
- Saved source evidence, model contract, README and this work log. No raw changes, commit/push, scheduling or ML feature/training work in this step.

## Step 6 - station/date dimensions and hourly flows (2026-10-21)

Created four full-rebuild tables in the existing US intermediate/marts datasets and added scoped schema resolution. Existing staging relation destinations are unchanged.

Four tables created; 31 distinct data tests passed, with no unresolved failure or warning. The initial build passed 30 tests and encountered a SQL syntax error in the date-continuity test. That test was repaired and rerun successfully; models and other tests were unchanged.

- marts.dim_station: 627 rows.
- marts.dim_date: 300 rows.
- intermediate.int_trip_endpoints_hourly: 2,615,657 rows.
- marts.fct_station_hourly_flows: 1,737,138 rows.

All 3,527,328 staged rides had valid time quality and contributed both endpoints. The intermediate preserves all 7,054,656 endpoints. The mapped fact contains 3,524,722 departures and 3,519,472 arrivals; 2,606 departure and 7,856 arrival endpoints are retained only in the intermediate because their codes are missing/unmapped. Thus aggregate mapped net flow is -5,250, an explained mapping difference.

Calendar: 2025-12-31 through 2026-10-26 (300 dates, including forecast-weather dates). The mapped fact covers 620 stations and 1,737,138 observed station hours. March 8, 2026 has 23 distinct observed UTC hours and no local 02:00 rows, consistent with spring-forward handling. See dimension-hourly-verification-2026-10-21.json for counts, partitions and final test statuses.

No commit, push or PR was made. Next: inventory observation history and its quality/coverage contract, before point-in-time ML features.

## Step 7 - inventory observation history (2026-10-21)

Created fct_station_inventory_history and inventory_collection_quality in the existing US marts dataset. Prior raw, staging, dimensions and flow relations are unchanged.

- marts.fct_station_inventory_history: 3,762 rows, all staged status observations retained; 627 stations across 6 irregular collections.
- marts.inventory_collection_quality: 6 snapshot summaries.
- Strict bike and dock usable observations: 3,712 each. The 50 remaining observations are retained with null strict binary outcomes: 12 invalid report timestamps, 12 stale reports, 12 otherwise valid but closed to renting/returning, and 14 capacity-review observations.
- Existing staging usability remains 3,726; the stricter history layer additionally screens the 14 capacity contradictions. This is conservative eligibility, not a conclusion that all 14 are corrupt.
- Repeated valid station-report timestamps in consecutive collections: 694. Regressed valid source reports: 0. No missing prior station metadata or future metadata joins were found.
- Longest gap between observed station collections: 141,946 seconds (about 39.4 hours). No unobserved inventory was synthesized.
- Latest collection: 2026-10-20 01:51:09 UTC / 2026-10-19 21:51:09 America/New_York. It is older than 120 minutes at verification.
- dbt parse passed. The selected build created 1 table and 1 view and ran 28 data tests: 26 pass, 2 warnings, 0 failures/errors/skips. Warning rows: 14 capacity-review observations and 1 stale latest collection. CLI PASS=28 includes the two successful models.

See [verification record](inventory-history-verification-2026-10-21.json) for aggregated coverage and all test results. Source-data warnings remain visible rather than changing thresholds to hide them.

No source collection, model training, commit, push or PR was performed. Next: point-in-time feature/label eligibility and actual sample coverage.

## Step 8 - availability features, labels and actual sample coverage (2026-10-21)

Built request, feature, label, training-ready and coverage relations; added policy validation and scoped ml dataset resolution. Raw and upstream warehouse objects were not rewritten by the selected build.

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

See [verification evidence](availability-ml-verification-2026-10-21.json) for policy, code hashes, source times, exact model/test results and per-origin counts. No commit, push, PR, training, score or serving deployment was performed.

Next: integrated dbt verification and reviewable ML/ingestion handoff; no automatic change to a proxy target.

## Step 9 - integrated verification and role handoff (2026-10-21)

Completed the full 16-model build, 140 data tests (134 pass, 6 warnings), 1 passing synthetic unit test, connection and dependency checks. No build errors/skips. The dependency graph has no cycles and targets the intended US datasets. Independent freshness reports station status ERROR STALE, forecast weather WARN and station information PASS. The data still has 6 irregular inventory collections and zero matched availability training labels.

Documented the weather weekly-schedule versus 36/48-hour freshness mismatch and the absence of a dbt invocation in inspected DAG Python files. Added an actionable Erica/Danish/Rahul/George handoff and updated the root/dbt READMEs. No schedule, freshness threshold, source collection, training, credentials or permissions changed. A reviewable PR description was prepared outside the repo. No commit, push, PR creation or Slack message was performed.
