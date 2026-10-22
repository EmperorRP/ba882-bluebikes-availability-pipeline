# BA882 Bluebikes Availability Pipeline

Forecast Bluebikes station availability to help riders plan trips and support rebalancing decisions.

## Proposed architecture

GBFS station information/status, historical trips, and weather feed immutable raw objects in GCS. BigQuery and dbt provide tested analytical models and time-aligned features. A versioned model publishes forecasts to an app/API. Airflow/Astronomer coordinates refreshes and retraining.

## Repository map

- `ingestion/`: source discovery, validation, and raw ingestion.
- `orchestration/dags/`: refresh, transformation, and retraining workflows.
- `warehouse/`: BigQuery schemas and loading contracts.
- `dbt/`: transformations, tests, and lineage.
- `ml/`: training, evaluation, and serving.
- `app/`: station availability interface.
- `infra/`: repeatable resource configuration.
- `tests/`: focused component and integration checks as implementation grows.
- [`docs/`](docs/README.md): documentation organized by dbt, pipeline, ingestion, and architecture.
  - [Pipeline status and integration guide](docs/pipeline/pipeline-status.md): current workstream status, deployment gates, and integration sequence.

## Development

Implementation dependencies and setup commands will be defined in OPS-01. Keep credentials and raw data outside Git; provide only placeholder configuration in `.env.example`. Use feature branches and pull requests. Each PR should identify its issue, explain the change, and include appropriate validation.

## Backlog

Initial issues are ARCH-01, ING-01 through ING-03, WH-01, DBT-01, ML-01, APP-01, OPS-01, and DOC-01. Current data-layer delivery and ingestion/ML responsibilities are documented in the [dbt handoff](docs/dbt/dbt-handoff-2026-10-21.md).

## Verified data-layer status (2026-10-21)

The BigQuery/dbt layer has 16 integrated models, 140 data tests (134 pass, 6 documented warnings) and 1 passing unit test. Read the [handoff and runbook](docs/dbt/dbt-handoff-2026-10-21.md) and [verification evidence](docs/dbt/evidence/dbt-integrated-verification-2026-10-21.json). Status ingestion is stale and weather freshness needs an agreed schedule/SLA. The current availability feature/label contract has 15,048 requests but zero matched real labels and zero training rows; continuous collection and ML review remain necessary.

## Integration verification (2026-10-22)

An independent build reproduced all 16 models, 134 passing data tests, six documented warnings and one passing SQL unit test in isolated review datasets. The expanded unit test covers the five-minute collection cadence and its 15-minute label window; credential-free dbt parse CI is included. See the [review evidence](docs/dbt/polling-label-review-2026-10-22.md).

Ingestion PR #17 is deployed to Astro: scheduled GBFS, weather and trip tasks succeeded, and the three configured source-freshness checks passed after raw data refreshed. Shared dbt builds are not scheduled in Astro yet; automatic transformation orchestration, sustained collection and ML policy/coverage review remain the next integration work. The initial approved Astro wake override ends on October 22 at 19:43 UTC (3:43 PM America/New_York).
