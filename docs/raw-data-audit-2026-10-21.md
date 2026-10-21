# Raw-data audit - 2026-10-21

Read-only inspection from Marcus's Cloud Shell. Project: ba882-bluebikes-pipeline. BigQuery datasets raw, staging, intermediate, marts, ml all use US. Counts are a point-in-time audit, not a pipeline SLA. No source data was modified.

| Table | Records | Notes |
| --- | ---: | --- |
| raw.station_information | 3,135 | 627 stations, 5 snapshots |
| raw.station_status | 3,762 | 627 stations, 6 snapshots |
| raw.historical_trips | 3,527,328 | Jan-Sep 2026 source files |
| raw.weather_hourly | 7,872 | 6,864 historical + 1,008 forecast-version rows |

## Observations

- GBFS status collection spans 2026-10-18 02:17:30 UTC to 2026-10-20 01:51:09 UTC (Oct 17 22:17 to Oct 19 21:51 America/New_York). Six batches do not establish continuous 30-minute collection.
- Both GBFS tables are partitioned by ingested_at_utc and clustered by station_id. Trip and weather tables currently have neither partitioning nor clustering. No tables were migrated.
- No duplicate station_id/snapshot_id keys were found. Station counts are non-null/nonnegative. Station information has no missing capacity or coordinates.
- Trips have no missing/duplicate ride_id, missing start/end timestamp, or negative duration. Missing start station IDs: 1,923; missing end station IDs: 7,234.
- Of 623 distinct nonempty trip start station IDs, zero match GBFS station_id directly. GBFS raw_json.short_name matches 620 IDs, covering 3,524,722 trip rows. This result covers start IDs; end-ID matching and mapping uniqueness still need verification.
- Thirty rides in the January source file start in December 2025; two inspected examples finish in January. This is a month-boundary observation, not by itself a data error. Original trip timezone semantics remain unverified.
- Twelve status records have last_reported before 2020. Twenty-four reports are more than 60 minutes older than collection; none of those rows is renting. Preserve and flag these operational states rather than blindly using them as fresh inventory.
- Historical weather covers Jan 1-Oct 13 inclusive in UTC. Forecast API rows cover Oct 12-Oct 26 across versions. There are 336 legacy forecast rows with null forecast_issued_at, plus two timestamped versions of 336 rows each.
- Weather checks found no null key weather values or negative precipitation/wind and no out-of-range humidity. Forecast fetch time is not provider issuance time. API past_days rows must not be treated as historical forecasts available before fetch time.

## Next actions

Initialize dbt, build a validated station-ID bridge, define time and snapshot-quality flags, then stage raw data. Coordinate continuous cloud ingestion with Erica/Rahul and the feature/target time contract with Danish. Availability training remains limited by snapshot coverage.

## Time follow-up

The subsequent trip/weather increment compared the original March CSV with BigQuery and inspected DST behavior. America/New_York is now used as an explicit evidence-backed inference, not an operator-confirmed declaration. Raw timestamps remain unchanged. See trip-weather-model-contract.md and trip-time-evidence-2026-10-21.json.
