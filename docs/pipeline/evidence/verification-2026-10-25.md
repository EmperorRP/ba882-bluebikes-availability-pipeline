# Cloud verification summary — October 25, 2026

## Delivered

- [PR #19](https://github.com/EmperorRP/ba882-bluebikes-availability-pipeline/pull/19) reconciled the moved documentation and added the [implemented data model](../../architecture/data-model.md): relationships, logical keys, row grains and SQL lineage.
- [PR #20](https://github.com/EmperorRP/ba882-bluebikes-availability-pipeline/pull/20) deployed freshness-gated dbt after daily weather and monthly trip ingestion. Reviewed source revision: `476856c`.
- dbt dependencies are isolated from Airflow. The production build uses the existing cloud workload identity, with approved dataset-scoped access and serialized builds. No credential key or project-wide Editor/Owner was added.
- Fourteen tests in the real Astro runtime, both dependency checks, credential-free dbt parse and all three GitHub CI checks passed. Astro CLI's separate default integrity test was skipped because its default test file is absent; that skip is not a passing test.

## Cloud execution

The deployment was healthy with zero import errors during the approved verification window. An actual scheduled weather run completed **ingestion -> source freshness -> warehouse build**, all on the first attempt. Station snapshots repeated on their five-minute schedule.

The weather run executed late after hibernation; this is not proof of an on-time daily SLA. Pending logical intervals do not backfill missed station observations. The trip DAG's new three-task graph is deployed and runtime-tested, but full monthly ingestion was not rerun in this window; the prior ingestion-only cloud success was October 22.

Warehouse verification returned **16 successful models (7 tables, 9 views), 135 passing data tests, 5 warning data tests, 1 passing SQL unit test and 3 passing source-freshness checks**. The result artifact's aggregate 136 passes includes the unit test, not 136 data tests. Trips have no configured freshness SLA.

## Observed data and ML readiness

| Raw source | Rows | Collections |
| --- | ---: | ---: |
| Station status | 36,418 | 58 |
| Station information | 35,791 | 57 |
| Historical trips | 3,527,328 | — |
| Weather hourly | 9,336 | — |

The shared derived coverage had been outdated. Rebuilding incorporated later raw collections and produced real short-horizon labels:

| Horizon | Requests | Observed labels | Training-eligible rows | Distinct labelled origin times |
| --- | ---: | ---: | ---: | ---: |
| 1 hour | 36,418 | 22,466 | 22,341 | 36 |
| 3 hours | 36,418 | 7,494 | 7,431 | 12 |
| 6 hours | 36,418 | 0 | 0 | 0 |
| 24 hours | 36,418 | 0 | 0 | 0 |

**Not yet ready for defensible ML evaluation.** Eligible origins cover only one Boston date; thousands of station rows are not independent time periods. Class counts are 1,453 no-bike / 20,888 has-bike at 1 hour and 402 / 7,029 at 3 hours. Continuous, budget-approved collection and a reviewed chronological split/embargo remain necessary. These results do not establish mature future labels for the new verification window.

Five warning tests remain visible: `station_report_quality_warning`, `weather_forecast_version_warning`, `trip_station_mapping_gaps_warning`, `inventory_capacity_review_warning` and `availability_insufficient_labels_warning`. Interpret and address them rather than suppressing tests.

## Evidence privacy and operating boundary

The user requested that **original screenshots and detailed cloud audits remain local**. They are not committed to this public repository. Local records preserve actual execution times, query job IDs, cloud resource identifiers, usage metrics and immutable artifact references for private review and presentation preparation. This public page is an aggregate summary, not the detailed audit.

Only the approved up-to-four-hour verification window was authorized. It was not extended, and the normal wake policy was not changed. Ongoing funding and a continuous collection window remain decisions for the course/organization billing owner. Trial duration and a billing-account name do not establish a remaining credit balance; per-query limits do not cap the invoice. No new billing API was enabled.

[Operating decision](../operating-policy.md) · [Presentation outline](../../presentation/README.md)
