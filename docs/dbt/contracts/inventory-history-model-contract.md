# Station inventory observation history

## Published relations and grain

marts.fct_station_inventory_history is a full-rebuilt BigQuery table at station_id + snapshot_id grain. It preserves every staged status row and every existing source/quality field, adds a deterministic observation hash, known-at-collection station metadata, conservative bike/dock usability, fill ratios, collection gaps and repeat-report flags. It is partitioned by UTC collection date and clustered by station_id in US.

marts.inventory_collection_quality is a view with one row per observed snapshot_id. It summarizes station/observation counts, strict usable observations, report-time suspects, capacity reviews, missing prior metadata, repeated or regressed reports and the largest preceding station collection gap. Counts describe observations, not an independently verified complete station universe.

## Three distinct times

- reported_at_utc is the station's source report time. Invalid or stale source reports remain in history.
- snapshot_at_utc is the raw ingested_at_utc, the earliest availability boundary recorded by this warehouse. source_available_at_utc explicitly preserves this boundary. It is not a separately measured API response time or proof of real-time transformation latency. A simulation cannot use the observation before this boundary.
- metadata_available_at_utc is the latest station-information ingestion not later than this status ingestion, tied deterministically by snapshot ID. Names, trip codes and capacity are not taken from the latest current dimension. This is metadata known at collection time, not proof of a historical metadata version at the station's reported time.

The two GBFS feeds are sampled separately. Capacity disagreements are review signals; their cause is not established. Original counts are never clamped to capacity or deleted.

## Usability and nullable observations

The source staging fields is_usable_inventory_observation and has_bike_observed retain their prior definitions unchanged. This history adds stricter fields is_bike_observation_usable and is_dock_observation_usable:

1. Source report_time_quality is valid, with nonnegative report_age_seconds (thus the report cannot be after collection). The inherited age limit is 60 minutes. A future forecast may need a tighter horizon-specific freshness rule.
2. Bike and dock counts are non-null and nonnegative.
3. Capacity known at collection is positive and bike + dock counts do not exceed it.
4. Station and snapshot identities are present, and the corresponding is_renting or is_returning flag is true.

has_bike_observed_strict and has_dock_observed_strict are null on unusable observations. They become true/false only for an eligible observation with at least one / zero corresponding units. Ineligible observations must not become negative training labels. Fill ratios are null when capacity consistency cannot be established, and otherwise use the known-at-collection capacity.

The conservative capacity rule may exclude plausible observations; preserve capacity_check so the team can review them rather than silently treating them as proven corruption. Strict usability is a collection-time data-quality screen, not certification of training suitability or current availability.

## Repetition, gaps and freshness

Every collection remains in history. is_repeated_station_report compares the current valid report timestamp with the preceding collection for that station. report_time_regressed flags an earlier source report timestamp relative to that preceding collection. They are null when the comparison is unavailable or the current report is invalid. Repeated reports are not automatically removed: unchanged values can still be an actual collection, but repeated collections must not be counted as independent source updates. Neither report flag invents a fresh station report time.

seconds_since_previous_collection exposes collection gaps. No hourly inventory interpolation, forward-fill, synthetic snapshots or source coverage assumptions are introduced. A missing collection cannot prove an empty station.

The quality view computes collection_age_seconds_now and is_collection_stale_now at query time, with the existing 120-minute status freshness threshold. Historical row usability remains evaluated at collection time. A good observation collected days ago is not current inventory. Latest-collection freshness is a warning test in this history increment; the raw source freshness check retains its separately configured error threshold.

## Validation and reproduction

With staging, dim_date and the Cloud Shell OAuth profile already available:

    dbt parse
    dbt build --select tag:inventory_history

Tests cover observation/snapshot keys, allowed quality categories, calendar relationships, preservation of every staged source field, latest prior metadata selection, operational/nullable-outcome rules, bounded ratios, collection times and summary reconciliation. Separate warnings expose capacity-review records and stale latest collection. Prior staging and flow tests are not rerun by this selected build.

The latest verification record contains actual counts, warning rows, collection coverage, table partitioning and test results. No source collection, ingestion deployment, prediction target, point-in-time feature join, training run or GitHub publication is part of this increment.

## Next boundary

Inventory history is the source for later point-in-time feature/label models. Such models must define prediction origins, horizons, report-age limits and label observation tolerance; require source availability no later than the origin for features; and retain unavailable labels as null. Only a few irregular collection batches exist, which cannot support a reliable availability forecast backtest. Continuous status collection and sufficient longitudinal history remain necessary.

## Verified on 2026-10-21

- marts.fct_station_inventory_history: 3,762 rows, all staged status observations retained; 627 stations across 6 irregular collections.
- marts.inventory_collection_quality: 6 snapshot summaries.
- Strict bike and dock usable observations: 3,712 each. The 50 remaining observations are retained with null strict binary outcomes: 12 invalid report timestamps, 12 stale reports, 12 otherwise valid but closed to renting/returning, and 14 capacity-review observations.
- Existing staging usability remains 3,726; the stricter history layer additionally screens the 14 capacity contradictions. This is conservative eligibility, not a conclusion that all 14 are corrupt.
- Repeated valid station-report timestamps in consecutive collections: 694. Regressed valid source reports: 0. No missing prior station metadata or future metadata joins were found.
- Longest gap between observed station collections: 141,946 seconds (about 39.4 hours). No unobserved inventory was synthesized.
- Latest collection: 2026-10-20 01:51:09 UTC / 2026-10-19 21:51:09 America/New_York. It is older than 120 minutes at verification.
- dbt parse passed. The selected build created 1 table and 1 view and ran 28 data tests: 26 pass, 2 warnings, 0 failures/errors/skips. Warning rows: 14 capacity-review observations and 1 stale latest collection. CLI PASS=28 includes the two successful models.

See [verification record](../evidence/inventory-history-verification-2026-10-21.json) for aggregated coverage and all test results. Source-data warnings remain visible rather than changing thresholds to hide them.

## Availability feature/label follow-up

The [availability data contract](availability-ml-data-contract.md) is now implemented and tested. The current real observations produce no matched labels under the documented horizons/tolerance; inventory usability is not training readiness.
