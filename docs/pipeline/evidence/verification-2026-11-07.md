# Continuous collection and label coverage audit — 2026-11-07

Read-only BigQuery queries against `ba882-bluebikes-pipeline` (US) on 2026-11-07. Counts are point-in-time aggregates. Query job IDs and row-level output are not published. No warehouse objects were changed.

## Station snapshot collection (`raw.station_status`)

Collection has run continuously every five minutes since **2026-10-29 10:24 America/New_York**. The team has confirmed that collection continues through **2026-11-11**.

| Boston date(s) | Collections per day | Notes |
| --- | --- | --- |
| Oct 17, 19, 22, 25 | 2, 4, 49, 50 | Earlier bounded verification windows |
| Oct 29 | 164 | Continuous collection starts at 10:24 |
| Oct 30 – Nov 6 | 288 | Full days. Nov 1 has 300 because of the 25-hour DST fall-back day |
| Nov 2 | 177 | **Only gap: 09:30–18:52 local (562 minutes)** |
| Nov 7 | 270 at audit time | Latest collection 22:25 local |

Each collection holds about 628 station rows. Snapshots missed during the Nov 2 gap cannot be backfilled from live GBFS.

## Training-ready labels (`ml.station_availability_training_ready`)

The shared marts were rebuilt by the scheduled dbt build at 2026-11-07 06:08 UTC (`marts.mart_station_availability_features`: 6,244,128 requests; `marts.fct_station_inventory_history`: 1,561,032 observations).

| Horizon | Eligible rows | No bike | Has bike | No-bike share | Distinct origin times | Boston origin dates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 h | 1,499,372 | 106,670 | 1,392,702 | 7.11% | 2,430 | 12 |
| 3 h | 1,438,722 | 102,215 | 1,336,507 | 7.10% | 2,334 | 11 |
| 6 h | 1,377,517 | 97,997 | 1,279,520 | 7.11% | 2,237 | 9 |
| 24 h | 1,219,419 | 84,346 | 1,135,073 | 6.92% | 1,986 | 9 |

Compared with the [October 25 audit](verification-2026-10-25.md), which found 36 and 12 distinct 1 h and 3 h origin times on one Boston date and no 6 h or 24 h labels, the temporal coverage blocker is largely resolved. The data now include mornings, nights and two weekends. Rows from the same collection are still not independent samples, so evaluation must use a chronological split with an embargo.

24 h is the primary ML horizon. Its labels currently cover origins through Nov 6, because a 24 h label needs collection a day after the origin. With collection ending Nov 11, the last 24 h origins are on Nov 10.

## Lag-join rewrite check (PR #23)

The pre-PR #23 lag join, which ranked every candidate with `row_number`, and the new interval join were run side by side on the same current data for a deterministic 5% station sample (`mod(abs(farm_fingerprint(station_id)), 20) = 0`).

| Metric | Old | New |
| --- | ---: | ---: |
| Prediction rows | 308,488 | 308,488 |
| `lag_bikes` null rate | 0.096% | 0.096% |
| `has_lag_inventory` rate | 95.42% | 95.42% |
| Rows that differ (lag observation, bikes or flag) | — | **0** |

On the full table, BigQuery rejected the old pattern for exceeding the on-demand CPU limit: about 123k CPU-seconds against a limit of about 50.6k. This confirms the reason for the rewrite.
