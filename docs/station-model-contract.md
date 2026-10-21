# Station staging and ID mapping contract

Owner: Marcus (Person 3). Implemented under DBT-01 on 2026-10-21 in feature/marcus-dbt-foundation.

## Published views

All three are logical views in ba882-bluebikes-pipeline.staging (US). Raw tables are unchanged.

| View | Grain | Verified records |
| --- | --- | ---: |
| stg_station_information | station_id + snapshot_id | 3,135 |
| stg_station_status | station_id + snapshot_id | 3,762 |
| bridge_station_ids | station_id; trip_station_id also unique | 627 |

Both staging models normalize blank identifiers, retain collection lineage, and deduplicate within station_id/snapshot_id. Source-key reconciliation checks both missing and unexpected keys. The snapshot ID is opaque; do not parse legacy hashes as timestamps.

## Identifier mapping

Use trip start_station_id/end_station_id = bridge_station_ids.trip_station_id, then bridge_station_ids.station_id = stg_station_status.station_id. Preserve IDs as strings. Mapping codes come from raw station_information.raw_json.short_name.

All 627 observed GBFS station IDs have exactly one short code, with no conflicting pairs across the collected metadata snapshots. The bridge selects the latest metadata record for each station. It is a latest-known mapping, not a historized dimension and not proof of station identity before the collection period. Mapping reassignment causes hard tests to fail; define validity ranges before allowing changed mappings into ML features.

Both trip endpoints contain three nonempty codes absent from the collected GBFS metadata:

| Code | Example name | Start records | End records |
| --- | --- | ---: | ---: |
| C32118 | Melnea Cass Blvd at Hampden St | 317 | 339 |
| X32999 | 18 Dorrance Warehouse | 355 | 272 |
| BCBS01 | BCBS Hingham | 11 | 11 |

Also missing: 1,923 start station IDs and 7,234 end station IDs. No name-based guesses or fabricated IDs are added. The warning test reports 8 endpoint/code groups: three unknown codes plus NULL, for each of start and end. These are grouped results, not eight individual trips. Future trip models should left join and retain an explicit mapping status.

## Time and observation quality

- snapshot_at_utc is the actual collection time copied from raw ingested_at_utc. It is neither the scheduled slot nor the source report timestamp.
- snapshot_at_local is an America/New_York DATETIME for display. UTC timestamps and snapshot IDs remain the event keys across DST changes.
- source_last_reported preserves original Unix seconds. reported_at_utc range-checks conversion; sentinel times remain visible.
- report_time_quality: invalid_timestamp if conversion fails or predates 2020; future_report if over five minutes after collection; stale_report if over 60 minutes before collection; valid otherwise. These are explicit initial project policies.
- is_usable_inventory_observation requires valid report timing at collection, renting enabled, valid counts, and required identifiers. It does not claim that this collection is fresh now. Invalid 0/1 source flags become NULL and fail the operational-field test.
- has_bike_observed is bikes_available >= 1 for usable observations and NULL otherwise. It describes the collected observation, not a prediction or a future ML target.

Verified classification: 12 invalid-timestamp records, 12 stale-report records, 3,738 valid-timing records. Of the latter, 3,726 are usable and 12 are not renting. All 3,762 status records are retained. Source freshness remains a separate check, and the earlier collection-gap finding is unresolved.

## Validation and rerun

From the configured dbt environment:

```bash
dbt build --select tag:station_foundation
```

First build: 3 views created; 22 data tests executed, 20 passed and 2 warned; zero failed or skipped. Build exits 0. The CLI PASS=23 includes the three successful model builds.

Hard checks cover key nullability, composite uniqueness, count/coordinate ranges, station relationships, mapping uniqueness/stability, and source-key preservation. Warning checks surface 24 suspect inventory records and the 8 trip mapping-gap groups. These warnings are visible data limitations, not waived hard-test failures.

## Brighton Center example

Verified trip code D32028 maps to GBFS ID f83512c9-0de8-11e7-991c-3863bb43a7d0. A query through the bridge returns the latest collected Brighton Center record: Oct 19, 2026 at 21:51:09 America/New_York, 3 bikes and 14 docks. This is an old observation, not current availability and not tomorrow's forecast.

## Next boundary

Trip/weather staging is now available; the [trip/weather contract](trip-weather-model-contract.md) records the CSV/DST-based timezone inference and its limits. Point-in-time inventory features and target labels require a separate forecast-origin/target-time contract with Danish. Continuous source collection and orchestration remain with Erica/Rahul.
