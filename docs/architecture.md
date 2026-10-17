# Architecture

ARCH-01 owns the architecture decision. Proposed flow: source feeds → GCS raw → BigQuery → dbt → ML → app/API, coordinated by Airflow/Astronomer.

Confirm business metrics, prediction target/horizon, interfaces, cadence, regions, cost limits, and operational boundaries before implementation. Historical trips measure flows; exact station inventory requires station-status observations.
