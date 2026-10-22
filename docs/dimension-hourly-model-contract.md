# Station/date dimensions and hourly trip flow contract

## Published relations

- marts.dim_station: one latest observed GBFS station_id, with trip code, metadata and first/latest observation times. Metadata is not historized; an October observation is not proof of capacity, name or operation in January. Do not use it as historical/as-of metadata in training without a history policy.
- marts.dim_date: one New York calendar_date, continuous from the earliest to latest staged trip endpoint, station snapshot or weather valid date. Includes date key, year/quarter/month, weekday, weekend, ISO year/week and Monday week start. Date presence is not proof of source coverage; holidays are not inferred.
- intermediate.int_trip_endpoints_hourly: one UTC hour / departure-or-arrival / canonical station ID / original trip code / mapping status. Every valid staged ride contributes one departure and one arrival. Missing and unmapped codes remain visible with null canonical station ID. Invalid-time trips are excluded explicitly; reconcile their count separately rather than silently casting them to a valid hour.
- marts.fct_station_hourly_flows: one mapped station_id / hour_at_utc, with departures, arrivals, net_flow = arrivals - departures and total_endpoints. The unique hash is a convenience; the business key is station_id + UTC hour.

## Time, coverage and meaning

The trip interpretation inherits stg_trips' explicitly inferred America/New_York timezone (see trip-weather-model-contract.md). UTC defines hour identity; hour_at_local, local_date, local_hour and UTC offset are display attributes. During autumn fallback, equal local hours with different UTC timestamps remain separate.

The fact table is sparse: a row exists when at least one mapped endpoint was observed at that station/hour. A missing row does not prove zero rides. Within a present row, a zero departure/arrival count means none of that endpoint was found in currently loaded data. Completeness of source periods and station operating periods has not been established; do not build a dense zero-filled training grid from this table yet.

Net trip flow is not inventory change: rebalancing, maintenance, disabled bikes and other adjustments are not represented. Mapping exclusions also mean summed mapped departures and arrivals need not balance globally. The endpoint intermediate preserves the excluded counts for reconciliation.

first_source_ingested_at_utc and latest_source_ingested_at_utc describe contributing loaded records. These tables rebuild latest history and use the latest known station bridge. They are NOT point-in-time feature tables. Later ingestion can revise earlier hours; historical prediction joins require source availability and mapping-history controls. No rolling features, prediction labels, forecast-weather joins or model training are added in this step.

## Storage and schema resolution

These four relations are full-rebuilt BigQuery tables in US. The two hourly tables are partitioned by UTC event date and clustered by station; the endpoint table additionally clusters mapping status and endpoint type. No raw table is modified.

The project's bluebikes_use_shared_schemas=true enables generate_schema_name to resolve explicit intermediate/marts schemas exactly when the profile dataset is staging. Staging models still resolve to the profile dataset. Other profile datasets retain dbt's prefixed schema behavior. Use an isolated project or a different profile dataset for independent development to avoid writing the team's shared marts. Compiled target relations were checked before creation; all four target tables were absent before this first build.

## Reproduce and validate

From the dbt project with the existing OAuth profile:

    dbt parse
    dbt build --select tag:dimension_hourly

The selected build includes generic key/category/relationship tests plus endpoint conservation against staged trips at each hour/code, mapped fact reconciliation, grain/value/calendar continuity and station-bridge checks. Prior staging tests are not rerun by this command. Freshness is a separate check; this step does not establish live ingestion freshness.

## Next boundary

Station inventory observation history is now published; see [inventory history contract](inventory-history-model-contract.md) for quality and freshness rules. Next agree prediction origins/horizons and point-in-time feature eligibility with ML. The existing few status snapshots cannot support a robust availability forecasting backtest yet. Calendar and trip flows alone do not resolve that limitation.

## Verified on 2026-10-21

Four tables created; 31 distinct data tests passed, with no unresolved failure or warning. The initial build passed 30 tests and encountered a SQL syntax error in the date-continuity test. That test was repaired and rerun successfully; models and other tests were unchanged.

- marts.dim_station: 627 rows.
- marts.dim_date: 300 rows.
- intermediate.int_trip_endpoints_hourly: 2,615,657 rows.
- marts.fct_station_hourly_flows: 1,737,138 rows.

All 3,527,328 staged rides had valid time quality and contributed both endpoints. The intermediate preserves all 7,054,656 endpoints. The mapped fact contains 3,524,722 departures and 3,519,472 arrivals; 2,606 departure and 7,856 arrival endpoints are retained only in the intermediate because their codes are missing/unmapped. Thus aggregate mapped net flow is -5,250, an explained mapping difference.

Calendar: 2025-12-31 through 2026-10-26 (300 dates, including forecast-weather dates). The mapped fact covers 620 stations and 1,737,138 observed station hours. March 8, 2026 has 23 distinct observed UTC hours and no local 02:00 rows, consistent with spring-forward handling. See dimension-hourly-verification-2026-10-21.json for counts, partitions and final test statuses.
