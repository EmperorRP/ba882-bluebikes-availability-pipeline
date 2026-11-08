# Machine learning

ML-01 defines the target and forecast horizon, compares persistence/seasonal baselines with a candidate model, uses chronological evaluation, and versions training inputs and artifacts. Deploy the selected model and define weekly retraining and rollback criteria.

## Scope (2026-11-07)

- **Target:** `target_has_bike`, meaning the station has at least one bike of any type available at the target time. Docks are not predicted.
- **Horizons:** **24 hours (1440 minutes) is the primary horizon.** 1, 3 and 6 hours (60, 180 and 360 minutes) are secondary.
- **Data window:** continuous five-minute snapshots from 2026-10-29 10:24 America/New_York through 2026-11-11, with one gap on Nov 2 from 09:30 to 18:52 local. Earlier scattered collections (Oct 17–25) are also present. Decide whether to include them before building the split.
- **Input:** `ml.station_availability_training_ready`. Current coverage is in the [Nov 7 audit](../docs/pipeline/evidence/verification-2026-11-07.md). The no-bike share is about 7%.
- **Evaluation:** chronological split with an embargo of at least the horizon plus the 15-minute label window between train and test (just over 24 h for the primary horizon). 24 h origins run from Oct 29 to Nov 10, about 12 days, so a 24 h embargo uses up a noticeable share of the data. Rows from the same collection are not independent samples.
