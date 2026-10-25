# Collection and label regression review

The existing 15-minute post-target label policy is retained. The label unit-test fixture now covers a station polled every half hour whose source reports precede each collection by 30 seconds. A target at 13:00 has reports at 12:59:30 and 13:29:30: neither qualifies. A separate five-minute collection produces a report at 13:04:30 and a real positive label.

These synthetic rows are dbt unit-test inputs, not additions to shared source tables or training data. The production polling change is proposed separately in PR #17. Faster collection creates more opportunities for usable labels, but report freshness, station usability, collection gaps and distinct periods/classes still determine training readiness.

The `dbt parse` workflow validates project configuration, models and test definitions using the pinned Python 3.12 development dependencies. It uses a credential-free parse-only profile and does not run warehouse SQL tests. A separate authenticated build/unit-test check is still required before merge or deployment.

## Independent BigQuery validation

Verified on 2026-10-22 using the team's existing raw sources and an isolated target dataset `review_rahul_20261022`, with derived datasets suffixed `_intermediate`, `_marts` and `_ml`. All datasets are in `US`; the shared transformation relations were not replaced. Each query was capped at 1,000,000,000 billed bytes.

- dbt Core 1.12.6 and dbt-bigquery 1.12.1 installed successfully in an isolated Windows Python 3.13.5 environment.
- Credential-free project parse passed. GitHub CI separately passed with the documented Python 3.12 environment.
- Full `dbt build` passed in 194.32 seconds: 16 successful models, 134 passing data tests, six warnings and one passing SQL unit test including the added polling cases. No errors or skips.
- Build invocation: `fa80464c-ed5d-4b9d-b1b2-dc50a6c5392a`; results generated at `2026-10-22T15:41:39.835448Z`.
- The warnings matched the handoff: 24 suspect station reports, 336 legacy unversioned forecast rows, eight trip-mapping categories, 14 capacity reviews, one stale latest collection, and four horizons without labels.
- Independent source freshness returned station-information WARN, station-status ERROR STALE and forecast-weather ERROR STALE at approximately `2026-10-22T15:42:15Z`. Freshness was not relaxed to obtain a successful model build.

The shared raw table still had six station-status collections and zero real labelled/training-ready rows at audit time. Synthetic unit-test success validates the SQL edge cases; live collection and sufficient observation coverage remain required before training.
