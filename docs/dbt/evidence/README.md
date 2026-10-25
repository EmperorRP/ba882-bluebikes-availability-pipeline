# dbt verification evidence

These are dated validation records, not a live health dashboard.

| Record | Scope |
| --- | --- |
| [Integrated verification — 2026-10-21](dbt-integrated-verification-2026-10-21.json) | Full build, tests, source freshness, and coverage |
| [Trip-time evidence — 2026-10-21](trip-time-evidence-2026-10-21.json) | Source timestamp interpretation |
| [Dimension/hourly verification — 2026-10-21](dimension-hourly-verification-2026-10-21.json) | Dimensions, hourly flows, and validation totals |
| [Inventory-history verification — 2026-10-21](inventory-history-verification-2026-10-21.json) | Observation eligibility, gaps, and quality checks |
| [Availability ML verification — 2026-10-21](availability-ml-verification-2026-10-21.json) | Feature/label policy, tests, and training coverage |
| [Polling and label-window review — 2026-10-22](../polling-label-review-2026-10-22.md) | Independent integration and regression review |

The JSON files were relocated without changing their contents. Embedded file paths and hashes describe the original verification layout and remain intact for provenance; consult [model contracts](../contracts/README.md) for the current documentation locations.

[dbt guide](../README.md) · [Handoff](../dbt-handoff-2026-10-21.md)
