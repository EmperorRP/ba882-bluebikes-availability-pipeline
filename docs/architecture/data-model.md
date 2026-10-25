# Implemented warehouse data model

Verified against the SQL and YAML on `main` on 2026-10-25. Project: `ba882-bluebikes-pipeline`; all BigQuery datasets use `US`. This describes implemented relations, not a trained forecasting model.

**Grain** means what one row represents. **PK** labels the tested logical unique key, not an enforced BigQuery primary-key constraint. **FK** labels a join reference; unmapped stations and unavailable outcomes can be null. IDs are strings and UTC timestamps identify event hours; Boston local timestamps are display/calendar attributes.

## 1. Analytics relationships

```mermaid
erDiagram
    DIM_STATION ||--o{ HOURLY_FLOWS : "station_id"
    DIM_DATE ||--o{ HOURLY_FLOWS : "calendar_date = local_date"
    DIM_DATE ||--o{ INVENTORY_HISTORY : "calendar_date = collection_local_date"
    STATION_INFORMATION o|--o{ INVENTORY_HISTORY : "station_id and latest metadata available by collection"
    STATION_STATUS ||--|| INVENTORY_HISTORY : "station_id + snapshot_id"
    COLLECTION_QUALITY ||--o{ INVENTORY_HISTORY : "snapshot_id"

    DIM_STATION {
        string station_id PK
        string trip_station_id UK
        string station_name
        timestamp latest_metadata_at_utc
    }
    DIM_DATE {
        date calendar_date PK
        int date_key UK
        boolean is_weekend
    }
    HOURLY_FLOWS {
        string station_hour_id PK
        string station_id FK
        timestamp hour_at_utc "station + UTC hour is business key"
        date local_date FK
        int departures
        int arrivals
        int net_flow "arrivals minus departures, not inventory"
    }
    STATION_INFORMATION {
        string station_id PK
        string snapshot_id PK
        string trip_station_id
        timestamp snapshot_at_utc
        int capacity
    }
    STATION_STATUS {
        string station_id PK
        string snapshot_id PK
        timestamp snapshot_at_utc
        timestamp reported_at_utc
        int bikes_available
        int docks_available
    }
    INVENTORY_HISTORY {
        string inventory_observation_id PK
        string station_id
        string snapshot_id FK
        timestamp snapshot_at_utc
        timestamp reported_at_utc
        timestamp metadata_available_at_utc
        date collection_local_date FK
        boolean is_bike_observation_usable
    }
    COLLECTION_QUALITY {
        string snapshot_id PK
        int station_count
        int observation_count
        boolean is_collection_stale_now
    }
```

The inventory-to-quality connection is aggregation: many observations belong to one collection summary. Information/status snapshot IDs are collection identifiers generated separately for each feed; **do not equijoin the two feeds on snapshot_id**. Inventory metadata is selected as-of the status collection using station ID and timestamp. `dim_station` is latest-known metadata, not a historical station dimension; inventory training uses the as-of metadata instead.

## 2. Prediction requests, features and outcomes

```mermaid
erDiagram
    INVENTORY_HISTORY ||--o{ PREDICTION_REQUESTS : "origin_observation_id"
    PREDICTION_REQUESTS ||--|| AVAILABILITY_FEATURES : "prediction_id"
    PREDICTION_REQUESTS ||--|| AVAILABILITY_LABELS : "prediction_id"
    INVENTORY_HISTORY o|--o{ AVAILABILITY_LABELS : "label_observation_id, eligible future report"
    AVAILABILITY_FEATURES ||--o| TRAINING_READY : "prediction_id, usable origin only"
    AVAILABILITY_LABELS ||--o| TRAINING_READY : "prediction_id, observed outcome only"

    INVENTORY_HISTORY {
        string inventory_observation_id PK
        string station_id
        timestamp snapshot_at_utc
        timestamp reported_at_utc
    }
    PREDICTION_REQUESTS {
        string prediction_id PK
        string origin_observation_id FK
        string station_id
        timestamp prediction_at_utc
        int horizon_minutes "60, 180, 360, 1440"
        timestamp target_at_utc
    }
    AVAILABILITY_FEATURES {
        string prediction_id PK
        boolean is_origin_usable
        int origin_bikes_available
        int bikes_available_lag
        boolean has_trip_history
        boolean has_forecast_weather
    }
    AVAILABILITY_LABELS {
        string prediction_id PK
        string label_observation_id FK "nullable"
        int target_has_bike "0, 1, or null"
        string label_status
    }
    TRAINING_READY {
        string prediction_id PK
        string station_id
        timestamp prediction_at_utc
        int horizon_minutes
        int target_has_bike "must be observed"
    }
```

A request exists for every observed station collection crossed with each configured horizon. Features use only information available by the prediction origin. The label is the earliest usable source report in `[target, target + 15 minutes]`; no candidate means null, not zero. A label row can exist without an observed outcome. A training row requires both a usable origin and an observed label. No future label provenance is used as a predictor.

## 3. Source-to-model lineage

Arrows below are dbt dependencies, not proof that the transformation is scheduled in Astro. `raw` has four source tables; the other boxes are the 16 dbt models.

```mermaid
flowchart TD
    RI[raw.station_information] --> SI[staging.stg_station_information]
    RS[raw.station_status] --> SS[staging.stg_station_status]
    RT[raw.historical_trips] --> ST[staging.stg_trips]
    RW[raw.weather_hourly] --> SW[staging.stg_weather]
    SI --> BR[staging.bridge_station_ids]
    BR --> ST
    SI --> DS[marts.dim_station]
    SI --> DD[marts.dim_date]
    SS --> DD
    ST --> DD
    SW --> DD
    ST --> EP[intermediate.int_trip_endpoints_hourly]
    EP --> HF[marts.fct_station_hourly_flows]
    SI --> IH[marts.fct_station_inventory_history]
    SS --> IH
    IH --> CQ[marts.inventory_collection_quality]
    IH --> PR[intermediate.int_availability_prediction_requests]
    PR --> FE[marts.mart_station_availability_features]
    IH --> FE
    EP --> FE
    SW --> FE
    PR --> LA[ml.mart_station_availability_labels]
    IH --> LA
    FE --> TR[ml.station_availability_training_ready]
    LA --> TR
    FE --> CO[ml.availability_sample_coverage]
    LA --> CO
```

The trip bridge maps provider trip short codes to canonical GBFS station IDs. Trips do not join GBFS directly on their raw station-code fields. Unknown/missing endpoint mappings remain visible upstream; the mapped hourly flow fact excludes unmapped endpoints. Hourly flow rows are sparse observed event hours, not a complete zero-filled station/hour grid.

## 4. Table/view grains and keys

| Dataset.relation | One row represents | Logical unique key |
| --- | --- | --- |
| raw.station_information | One station in one metadata collection | station_id + snapshot_id |
| raw.station_status | One station in one status collection | station_id + snapshot_id |
| raw.historical_trips | One currently loaded ride, with source lineage | ride_id |
| raw.weather_hourly | One weather valid hour, source and forecast-fetch version | weather_time + source + forecast_issued_at; legacy/historical fetch time may be null |
| staging.stg_station_information | One normalized station metadata observation | station_id + snapshot_id |
| staging.stg_station_status | One normalized station inventory observation | station_id + snapshot_id |
| staging.bridge_station_ids | One latest-known canonical station/trip-code mapping | station_id; trip_station_id also unique |
| staging.stg_trips | One normalized ride with nullable mapped endpoints | ride_id |
| staging.stg_weather | One weather valid hour/source/fetch version | weather_record_id |
| marts.dim_station | One latest-known GBFS station | station_id |
| marts.dim_date | One Boston calendar date | calendar_date; date_key also unique |
| intermediate.int_trip_endpoints_hourly | One UTC hour, endpoint type, canonical/raw station IDs and mapping status | endpoint_hour_id |
| marts.fct_station_hourly_flows | One mapped station and observed UTC event hour | station_hour_id; business key station_id + hour_at_utc |
| marts.fct_station_inventory_history | One station/status collection with as-of metadata and quality | inventory_observation_id; business key station_id + snapshot_id |
| marts.inventory_collection_quality | One status collection summary | snapshot_id |
| intermediate.int_availability_prediction_requests | One inventory origin and prediction horizon | prediction_id; business key origin_observation_id + horizon_minutes |
| marts.mart_station_availability_features | One prediction request with as-of predictors and coverage flags | prediction_id |
| ml.mart_station_availability_labels | One prediction request and nullable future outcome | prediction_id |
| ml.station_availability_training_ready | One usable, labelled request with an explicit predictor allowlist | prediction_id |
| ml.availability_sample_coverage | One configured horizon's coverage summary | horizon_minutes |

## Presentation boundaries

- Trip raw timestamps preserve the original unzoned CSV clock; staging applies the documented inferred Boston timezone. Do not silently reinterpret raw values as already-normalized UTC.
- Forecast fetch/warehouse availability times gate prediction features. Raw `forecast_issued_at` means collector fetch time, not confirmed provider issuance time.
- Net trip flow is not inventory change; missing observations or labels are not zero availability.
- A successful build validates software/data contracts, not current freshness, statistically adequate labels or forecasting accuracy.
- Use a dated coverage audit for actual row counts. The old handoff's counts are not a live dashboard.

[Model contracts](../dbt/contracts/README.md) · [Current pipeline status](../pipeline/pipeline-status.md) · [Documentation index](../README.md)
