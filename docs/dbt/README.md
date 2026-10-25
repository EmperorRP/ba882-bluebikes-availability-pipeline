# Bluebikes dbt project

Owner: Marcus (Person 3). Tracks [DBT-01](https://github.com/EmperorRP/ba882-bluebikes-availability-pipeline/issues/6), with warehouse contracts coordinated under WH-01.

## Documentation map

- [Handoff and responsibilities](dbt-handoff-2026-10-21.md)
- [Model contracts](contracts/README.md)
- [Verification evidence](evidence/README.md)
- [Work log](dbt-worklog.md)
- [Raw-data audit](raw-data-audit-2026-10-21.md)
- [Polling and label-window review](polling-label-review-2026-10-22.md)
- [All project documentation](../README.md)

## Current scope

The project configures dbt Core, a BigQuery OAuth connection, and four documented raw sources. The station increment now publishes two staging views and a station-ID bridge with 22 data tests. Trip/weather staging, station/date dimensions and hourly trip flows are published and tested. Inventory history and collection-quality monitoring are also published; availability feature/label contracts are also published. Real training remains pending sufficient labelled inventory history.

## Cloud Shell setup

Run from the repository root using Python 3.12 (validated environment):

```bash
python -m venv ~/.venvs/ba882-bluebikes-dbt
source ~/.venvs/ba882-bluebikes-dbt/bin/activate
python -m pip install -r dbt/requirements.txt
mkdir -p ~/.dbt/ba882-bluebikes
cp -n dbt/profiles.yml.example ~/.dbt/ba882-bluebikes/profiles.yml
export DBT_PROFILES_DIR="$HOME/.dbt/ba882-bluebikes"
export DBT_SEND_ANONYMOUS_USAGE_STATS=false
cd dbt
dbt debug
dbt parse
dbt ls --resource-type source --output name
```

Cloud Shell uses its existing Google application credentials. No key files or new IAM permissions are required for this setup. Keep the real profile outside Git; the example contains configuration only. Other environments need their own Application Default Credentials.

The checked BigQuery dataset location is **US**, including raw, staging, intermediate, marts and ml. The GCS bucket region us-east1 is not the BigQuery location. Staging views use the profile dataset (default staging); DBT_DATASET can override it. The three station models use this target dataset directly (default staging). The schema macro now resolves explicit intermediate/marts/ml models to the shared datasets when bluebikes_use_shared_schemas=true and the profile dataset is staging. Other profile datasets retain prefixed schema names; see the dimension/hourly contract.

## Sources

| dbt source | BigQuery table | Raw grain |
| --- | --- | --- |
| bluebikes.station_information | raw.station_information | station_id + snapshot_id |
| bluebikes.station_status | raw.station_status | station_id + snapshot_id |
| bluebikes.historical_trips | raw.historical_trips | ride_id |
| weather.weather_hourly | raw.weather_hourly | weather_time + source + forecast_issued_at (nullable in legacy rows) |

Column types reflect the live schemas inspected on 2026-10-21. Sources resolve under DBT_PROJECT, default ba882-bluebikes-pipeline. Use source('bluebikes', 'station_status') and source('weather', 'weather_hourly') in future models.

## Freshness policy

Run dbt source freshness separately from parsing. These initial thresholds express the desired cadence and may report failures against the current sparse collection; do not relax them merely to make checks green.

- Station status: warn after 60 minutes, error after 120 minutes, based on ingested_at_utc. This checks collection age, not each station's last_reported age.
- Station information: warn after 48 hours, error after 7 days, based on ingested_at_utc.
- Weather: warn after 36 hours, error after 48 hours, using forecast_issued_at only for forecast_api rows. Historical weather loads cannot mask stale forecasts. This column records fetch time, not provider issuance time.
- Trips: freshness disabled until the publication/discovery SLA and manifest are agreed. Ingestion time alone does not prove a new monthly file is available.

Legacy forecast rows with null forecast_issued_at are excluded from the forecast freshness maximum. They require separate quality flags before point-in-time ML use.

## Handoff limitations

The [raw-data audit](raw-data-audit-2026-10-21.md) records sparse GBFS coverage, station-ID mismatches, missing trip station IDs, and legacy forecast timestamps. Trip IDs cannot join GBFS station_id directly: build an explicit mapping from GBFS raw_json.short_name. Confirm trip timestamp semantics against the original source before timezone normalization. Do not infer continuous availability from trip histories or fill missing snapshots as observations.

## References

- [dbt BigQuery setup](https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup)
- [Source freshness configuration](https://docs.getdbt.com/reference/resource-configs/freshness)
- [Work log](dbt-worklog.md)

## Validation on 2026-10-21

Connection, parse and four-source discovery passed. Source freshness reports stale station status and a weather warning, matching the raw audit. See the work log for details. The initial foundation created no models. The subsequent station increment created three views; see the station model contract.

## Station models

See [station contracts, warnings and validation](contracts/station-model-contract.md). Run `dbt build --select tag:station_foundation` to rebuild the three views and execute their tests. The latest build has 20 passing tests and two explicit source-data warnings. Raw source data is unchanged.

## Trip and weather models

See [time, mapping and weather-version contract](contracts/trip-weather-model-contract.md). Run `dbt build --select tag:trip_weather_staging` with the station bridge already built. The step created two US staging views, preserving 3,527,328 rides and 7,872 weather rows; 29 tests passed and one warned about 336 legacy forecast rows. The trip timezone is an explicit CSV/DST-based inference, recorded with raw timestamps. Source freshness and cloud scheduling remain separate concerns.

## Station/date dimensions and hourly flows

See [grain, coverage and validation contract](contracts/dimension-hourly-model-contract.md). Run `dbt build --select tag:dimension_hourly` after staging exists. Four tables are published in intermediate/marts; 31 data tests passed after repairing and rerunning one test. Sparse event hours are not a complete station/hour grid, and net trip flow is not inventory change. The accompanying [verification record](evidence/dimension-hourly-verification-2026-10-21.json) retains the validation runs and totals.

## Inventory observation history

See [inventory history contract](contracts/inventory-history-model-contract.md) and [verification record](evidence/inventory-history-verification-2026-10-21.json). Run `dbt build --select tag:inventory_history` after staging and dim_date exist. The table retains 3,762 observations; 3,712 pass conservative bike/dock usability. The collection-quality view has 6 rows. Tests: 26 pass and two explicit warnings (14 capacity reviews; stale latest collection), with no errors. Collection-time usability does not imply current inventory or sufficient training history.

## Availability features and labels

See [availability ML data contract](contracts/availability-ml-data-contract.md) and [verification evidence](evidence/availability-ml-verification-2026-10-21.json). After upstream models exist, run `dbt build --select tag:point_in_time_ml`. Initial configurable policy: 1/3/6/24-hour horizons, 15-minute post-target label tolerance, 60-minute report age/lag and 56-day observed trip-code history. Five relations were created; 28 data tests and 1 synthetic unit test passed, with 1 explicit zero-label warning. The real feature/label tables each contain 15,048 requests but ZERO real outcomes and ZERO training-eligible rows. This is a data foundation, not a trained or deployable availability model.

## Integrated verification and handoff

On 2026-10-21, `dbt debug`, the pinned environment dependency check and the full `dbt build` passed. All 16 models succeeded; 140 data tests ran (134 pass, 6 warnings), plus 1 passing unit test, with 0 build errors/skips. Independent `dbt source freshness` returned a station-status ERROR STALE, a forecast-weather WARN and station-information PASS; trips have no agreed freshness SLA yet. The existing weather DAG is weekly while forecast freshness expects 36/48 hours, and no dbt invocation appears in the inspected DAG Python files. See the [handoff](dbt-handoff-2026-10-21.md) and [complete evidence](evidence/dbt-integrated-verification-2026-10-21.json). These operational/data-readiness issues remain open.
