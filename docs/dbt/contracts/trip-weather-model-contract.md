# Trip and weather staging contract

Owner: Marcus (Person 3), DBT-01, 2026-10-21. Published as logical views in ba882-bluebikes-pipeline.staging (US).

| View | Grain | Verified records |
| --- | --- | ---: |
| stg_trips | ride_id | 3,527,328 |
| stg_weather | weather_at_utc + source_type + forecast_fetched_at_utc | 7,872 |

Raw tables were not changed. Trip and weather models deduplicate only within their documented keys. Tests compare source and output business keys in both directions. All current source records survive. Weather forecast versions are not collapsed to the latest value for a valid hour.

## Trip timezone: evidence and explicit inference

The operator [system-data page](https://bluebikes.com/system-data) describes start/end times but did not specify their timezone in the inspected documentation. Do not cite this page as confirmation of Eastern time.

We downloaded the existing March source archive from GCS, read its CSV, and compared five ride IDs with raw BigQuery. The CSV values are unzoned clock strings, and BigQuery's UTC clock characters exactly match them. The current ingestion script loads TIMESTAMP columns without an explicit source timezone. For example, CSV 2026-03-05 08:50:23.824 was stored as 08:50:23.824 UTC.

Independent DST evidence in the original March CSV supports Boston local time:

| Date | Starts during 01:00 | Starts during 02:00 | Starts during 03:00 |
| --- | ---: | ---: | ---: |
| 2026-03-07 | 64 | 50 | 17 |
| 2026-03-08 | 103 | 0 | 106 |
| 2026-03-09 | 22 | 17 | 21 |

America/New_York is therefore an explicit, evidence-backed **project inference**, not a provider-confirmed fact. It is configured by trip_source_timezone in dbt_project.yml. The view records source_timezone and timezone_basis on each ride and retains raw_started_at/raw_ended_at for audit.

Conversion first recovers the CSV wall clock with DATETIME(raw_timestamp, 'UTC'), then interprets that wall clock in America/New_York. For the March 5 example, the resulting instant is 13:50:23.824 UTC. March 30 11:41:53.725 becomes 15:41:53.725 UTC, correctly accounting for DST. Milliseconds are preserved.

The model flags nonexistent local times, ambiguous fall-back times, missing times and negative durations. Current full-data checks find zero suspect times. Thirty-four rides have a different elapsed duration after DST conversion; this is expected for journeys crossing the spring clock jump. Future ambiguous-hour records remain present and must be excluded or resolved before hourly/event-time analytics.

**Loader boundary:** this logic applies to the current local-clock-stored-as-UTC encoding. If ingestion is changed to produce true UTC instants, update this staging contract at the same time. Applying the current reinterpretation to already-corrected UTC would shift timestamps twice.

## Trip identity and station mapping

ride_id is non-null and unique. rider_type normalizes member_casual; bike and rider categories are validated. start_trip_station_id/end_trip_station_id preserve the source codes, while start_station_id/end_station_id are canonical GBFS IDs from the latest-known bridge.

| Endpoint | Missing source code | Nonempty but unmapped code |
| --- | ---: | ---: |
| Start | 1,923 | 683 |
| End | 7,234 | 622 |

Missing and unmapped records are retained with mapping statuses. Do not inner join them away. Current metadata mapping is not a historical validity dimension; use the station contract's limitation when designing long-range historical ML features. started_hour_utc and ended_hour_utc support separate departure and arrival aggregation; use only valid-time records and a mapped code for the relevant endpoint.

## Weather clock, units and versions

Inspected original historical and forecast JSON records specify timezone GMT, utc_offset_seconds 0 and hourly time unit unixtime. Stored weather valid times therefore remain UTC, with a New York DATETIME for display. Original hourly units are Celsius, relative humidity percent, millimetres and km/h; no silent unit conversions are introduced.

The raw name forecast_issued_at actually records collector fetch time. The staging view calls it forecast_fetched_at_utc and does not invent provider issuance times. available_at_utc uses historical ingestion time, or the later of forecast fetch and ingestion time. Versions with missing timing metadata have NULL availability.

| Temporal role | Records |
| --- | ---: |
| historical_reanalysis | 6,864 |
| future_at_fetch | 333 |
| past_or_current_at_fetch | 339 |
| unversioned_forecast | 336 |

The Forecast API's past_days results are not forecasts that were available before they were fetched. is_future_at_available_time is true only for a version with valid timing and a future valid time at availability. A prediction-time join must still require available_at_utc <= prediction origin and choose the appropriate already-available version for the requested valid time.

Legacy forecast rows lack both fetch and ingestion times; they remain in staging, carry a quality warning and cannot be selected as future forecast candidates. Historical reanalysis is distinct from archived forecasts and must not silently replace them in a forecast backtest. Historical ingestion times may be updated by reloads, so treat them as conservative current-pipeline provenance rather than proof of original provider availability.

## Validation and rerun

With the existing station bridge already built:

```bash
dbt build --select tag:trip_weather_staging
```

The first build created 2 views and executed 30 tests: 29 pass, 1 warning, zero failed/skipped. The warning identifies 336 unversioned forecast rows. dbt's PASS=31 includes two successful model builds. The previous station increment's tests are separate; they were not unnecessarily repeated.

Checks include nullability, uniqueness, rider/bike categories, mapped station relationships, source-key preservation, physical ranges, timestamp quality and conservative forecast availability. No ML feature join or model training was performed.

## Follow-up

Build station/date dimensions and hourly arrivals/departures/net-flow models. Keep collection gaps and unknown mappings visible. Agree with Danish on forecast origin, target time, lag availability and weather backtesting before publishing ML features. See trip-time-evidence-2026-10-21.json for the source sample and DST counts.

References: [Open-Meteo historical API](https://open-meteo.com/en/docs/historical-weather-api), [station contract](station-model-contract.md), [work log](../dbt-worklog.md).

## Dimension/hourly follow-up

Station/date dimensions and hourly trip endpoint flows are now built and tested. See [dimension/hourly contract](dimension-hourly-model-contract.md); inventory history and point-in-time ML marts remain pending.
