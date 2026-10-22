# DBT-01 handoff — Bluebikes availability data

Owner: Marcus (Person 3). Prepared for Erica (ingestion/orchestration), Danish (ML), Rahul (project/deployment coordination), and George / Xingchen Ding (app). This document is a handoff artifact; it has not been sent to Slack.

## What is delivered

The Google Cloud project is ba882-bluebikes-pipeline. BigQuery raw, staging, intermediate, marts and ml datasets are US. The raw GCS bucket is ba882-bluebikes-pipeline-raw in us-east1; that bucket region must not be used as the BigQuery query location.

The dbt project now includes raw-source definitions, five staging/bridge views, station/date dimensions, hourly trip endpoint and station-flow tables, inventory observation history and quality, and availability prediction requests/features/labels/training/coverage relations. Model destinations and source-data limits are recorded in the contracts linked below. The latest integrated verification result accompanies this handoff.

This is a functioning, tested warehouse transformation layer. The current real availability training set has zero labelled samples under the initial 1/3/6/24-hour horizons and 15-minute post-target report window. No trained availability model, score, deployment or live app forecast is delivered by DBT-01.

## Erica: first priority is sustained source collection

1. Confirm the existing 30-minute GBFS collection schedule is actually deployed in a persistent runtime and running unattended. Cloud Shell commands and local Airflow tests alone do not establish continuous operation. Record successful runs, failed runs/retries, the scheduler/runtime and the owner.
2. Append station status and station information with real UTC ingestion/collection timestamps and stable collection IDs. Preserve last_reported as the station's source report time. A new collection of an unchanged report must not be presented as a newly updated station report. Preserve immutable originals and the existing idempotency/version contract.
3. Refresh forecast weather with both fetch and warehouse ingestion timestamps; preserve forecast versions. raw.forecast_issued_at currently means fetch time, not provider issuance. The 336 legacy unversioned forecast rows remain excluded from as-of forecast features.
4. Preserve historical trip originals and load provenance. Current raw trip TIMESTAMP values retain the original unzoned CSV clock, and staging interprets that clock as inferred America/New_York. If the raw loader starts producing true UTC instants, coordinate the staging change with Marcus to prevent shifting timestamps twice. Do not silently change the raw timestamp meaning.
5. Run dbt after successful raw loads with the correct OAuth/deployment identity and US location. Use the supported environment and runtime limits below. Coordinate the persistent deployment identity/runtime with Rahul; the verified development environment is the current Cloud Shell OAuth profile.
6. Inspect status freshness and availability_sample_coverage after collection. Accumulate longitudinal observations until each intended horizon has usable real outcomes over sufficiently many distinct time periods and classes for evaluation. Do not replace missing inventory, old reports or missing labels with zero or interpolated inventory.

Immediate acceptance evidence: advancing raw status max ingestion time; a sequence of new real collection batches with source report times; dbt build without errors; separately evaluated source freshness; increasing matched labels by horizon. A fresh snapshot or a large row count alone is not evidence of a statistically adequate model dataset.

### Schedule contract to resolve

The current code declares these schedules:

- orchestration/astro/dags/bluebikes_station_snapshot_dag.py: every 30 minutes.
- orchestration/astro/dags/weather_ingestion_dag.py: weekly (Monday at hour 6 in the DAG/runtime timezone).
- orchestration/astro/dags/bluebikes_trip_ingestion_dag.py: monthly (day 10 at hour 6 in the DAG/runtime timezone).

These are code declarations, not proof of deployment, timezone configuration or successful unattended runs. No invocation of dbt build/source freshness was found in the inspected DAG Python files; transformation orchestration should be confirmed explicitly.

The weekly weather schedule cannot continuously satisfy the currently configured 36-hour warning / 48-hour error freshness contract. Agree forecast refresh frequency with ML (a daily forecast refresh is a reasonable starting point) and the intended SLA, then implement the agreed orchestration. Historical weather backfills can have a separate cadence. No DAG schedule or freshness threshold was changed during this verification.

## Danish: review the contract, then assess actual sample adequacy

Use these relations:

| Need | BigQuery relation |
| --- | --- |
| Audit available features and source times | marts.mart_station_availability_features |
| Audit future outcomes and observation offsets | ml.mart_station_availability_labels |
| Eligible rows with explicit predictor columns and target | ml.station_availability_training_ready |
| Counts by horizon | ml.availability_sample_coverage |
| Real observed inventory and quality | marts.fct_station_inventory_history |
| Collection gaps and current collection age | marts.inventory_collection_quality |

Current primary outcome: target_has_bike, based on the earliest strict usable source report in [target, target + configured tolerance]. This is an observation near the target, not proof of exact-target inventory or availability throughout the interval. Dock prediction is not separately labelled in this increment.

Review the configurable horizon list [60,180,360,1440] minutes, label tolerance 15 minutes, report-age limit 60 minutes, inventory lag 60 minutes and trip lookback 56 days. These are versioned initial engineering settings pending ML/product review. Trip times retain an explicit CSV/DST-supported timezone inference, not provider confirmation.

Missing feature values remain null with coverage flags. Observed trip-code matching-hour counts are sparse historical event profiles, not complete daily demand means or historical stock. Historical code reuse and old source revisions require additional versioning for an exact backtest. Do not train with SELECT * from the feature or label audit tables: use an explicit predictor list, keep the future outcome as the target, and exclude provenance/IDs/raw timestamps from automatic predictor selection.

When enough outcomes exist, split chronologically, group repeated source reports/overlapping observations and apply a horizon/label-window embargo. Compare persistence/seasonal and simple statistical baselines before a candidate model; report class balance, coverage and performance by horizon and station. The current empty training view must not generate accuracy claims.

If the deadline requires a demand/shortage proxy, agree and name that alternative target with Rahul and Marcus, following [the architecture](../architecture/README.md). It must not be described as a trained true inventory-availability classifier. This handoff does not change the target automatically.

## Rahul and George: product and deployment boundary

Rahul should coordinate the persistent ingestion/dbt runtime, cloud identity and the decision on true availability versus a separately described proxy MVP. The current code branch and verification artifacts should be reviewed and published through the team's GitHub workflow before treating Cloud Shell-only files as a completed repository handoff.

George should keep observed inventory, its collection age and model forecasts distinct in the app. Current inventory snapshots are old; do not show them as live or present a missing forecast as a probability of zero. No serving/API forecast contract is implemented by this data-layer increment.

## Reproduce in the verified development environment

Cloud Shell repository: /home/mshi/ba882-bluebikes-availability-pipeline.

    cd /home/mshi/ba882-bluebikes-availability-pipeline
    source /home/mshi/.venvs/ba882-bluebikes-dbt/bin/activate
    export DBT_PROFILES_DIR=/home/mshi/.dbt/ba882-bluebikes
    export DBT_SEND_ANONYMOUS_USAGE_STATS=false
    cd dbt
    dbt debug
    dbt build
    dbt source freshness

A new developer should use [the dbt setup guide](README.md) and [profiles.yml.example](../../dbt/profiles.yml.example) with their own application credentials; do not copy credential files into Git. Dependencies are pinned in dbt/requirements.txt. The shared-schema variable maps explicit intermediate/marts/ml models exactly when the profile dataset is staging. For isolated work use a different target dataset/project rather than overwriting shared team relations.

The verified profile uses two threads and a 1 GB maximum bytes-billed limit per query. Keep the BigQuery location US. Build/test results and source freshness are separate: source status can correctly report ERROR STALE while model construction and data-contract tests pass. Warnings must be read and documented, not disabled to make a run green.

## Quick warehouse checks

Use the US query location:

    SELECT * FROM `ba882-bluebikes-pipeline.ml.availability_sample_coverage`
    ORDER BY horizon_minutes;

    SELECT * FROM `ba882-bluebikes-pipeline.marts.inventory_collection_quality`
    ORDER BY last_collected_at_utc DESC;

These aggregate queries report actual coverage and freshness; they do not train or serve a model.

## Contracts and evidence

- [dbt/README.md](README.md): setup, layer commands and validation history.
- [raw-data-audit-2026-10-21.md](raw-data-audit-2026-10-21.md): raw coverage and data issues.
- [station-model-contract.md](contracts/station-model-contract.md): station views, ID bridge and source report quality.
- [trip-weather-model-contract.md](contracts/trip-weather-model-contract.md): inferred trip timezone, trip mapping and versioned weather.
- [dimension-hourly-model-contract.md](contracts/dimension-hourly-model-contract.md): grains, sparse trip flows and net-flow meaning.
- [inventory-history-model-contract.md](contracts/inventory-history-model-contract.md): as-of metadata, strict eligibility, report repeats and gaps.
- [availability-ml-data-contract.md](contracts/availability-ml-data-contract.md): feature gates, label rule, unit cases and training limits.
- [dbt-integrated-verification-2026-10-21.json](evidence/dbt-integrated-verification-2026-10-21.json): full-build/freshness evidence for this handoff.
- [dbt-worklog.md](dbt-worklog.md): ordered work record.

## Integrated verification — 2026-10-21

- Development connection: dbt debug passed.
- Full build: all 16 models succeeded, with 0 errors and 0 skips.
- Data tests: 140 total; 134 pass and 6 warnings. One synthetic unit test passed.
- CLI total: PASS=151, WARN=6, ERROR=0, SKIP=0, TOTAL=157; successful models are included in CLI PASS.
- Dependency graph: 16 models ordered without cycles, resolving to the intended US staging/intermediate/marts/ml datasets.
- Independent source freshness: station_information PASS; station_status ERROR STALE; forecast weather WARN. Trip source freshness is intentionally disabled pending a monthly publication/discovery SLA, so this check covers three of four sources.
- Real inventory: 3,762 observations, 627 stations, 6 irregular collections; 3,712 strict usable observations. The longest observed collection gap is 141,946 seconds (about 39.4 hours).
- Latest status collection: 2026-10-20 01:51:09 UTC / 2026-10-19 21:51:09 America/New_York.
- Real availability requests: 15,048 across four horizons. Matched real labels: 0. Eligible training rows: 0.

| Data-test warning | Result and meaning |
| --- | --- |
| station_report_quality_warning | 24 source report-time suspects retained |
| trip_station_mapping_gaps_warning | 8 endpoint/code categories with missing/unmapped station IDs; not merely 8 rides |
| weather_forecast_version_warning | 336 unversioned legacy forecast rows |
| inventory_capacity_review_warning | 14 observations exceed known-at-collection capacity |
| inventory_latest_collection_freshness_warning | 1 stale latest collection |
| availability_insufficient_labels_warning | All 4 horizons have zero matched training labels |

The software build is validated; data freshness and training readiness require the actions above. Source freshness errors were preserved and recorded separately from build/test success. The working branch is feature/marcus-dbt-foundation, based on 88debb3. Changes remain uncommitted/unpushed at this handoff stage, and no Slack message was sent.
