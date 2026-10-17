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
- `docs/`: architecture, sources, and runbook.

## Development

Implementation dependencies and setup commands will be defined in OPS-01. Keep credentials and raw data outside Git; provide only placeholder configuration in `.env.example`. Use feature branches and pull requests. Each PR should identify its issue, explain the change, and include appropriate validation.

## Backlog

Initial issues are ARCH-01, ING-01 through ING-03, WH-01, DBT-01, ML-01, APP-01, OPS-01, and DOC-01. Team assignments remain undecided.
