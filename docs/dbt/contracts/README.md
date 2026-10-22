# dbt model contracts

| Contract | Scope |
| --- | --- |
| [Station models](station-model-contract.md) | Station staging, ID bridge, and report quality |
| [Trip and weather models](trip-weather-model-contract.md) | Trip timestamps, station mapping, and weather versions |
| [Dimensions and hourly flows](dimension-hourly-model-contract.md) | Station/date dimensions, table grains, and hourly trip flows |
| [Inventory history](inventory-history-model-contract.md) | As-of metadata, observation eligibility, repeated reports, and collection gaps |
| [Availability ML data](availability-ml-data-contract.md) | Features, labels, prediction horizons, and training eligibility |

See [verification evidence](../evidence/README.md) for dated validation records and [the dbt guide](../README.md) for setup and commands.
