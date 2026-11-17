-- One view over every horizon's forecasts (forecasts_h{H} from 06_publish) for the frontend.
-- Horizons included: ${horizons}. See docs/ml/forecast-serving-contract.md.
create or replace view `${project}.${dataset}.station_forecasts`
options (description = 'No-bike forecasts for all horizons (held-out test window). See docs/ml/forecast-serving-contract.md')
as
${forecast_union};

select horizon_minutes, model, count(*) as rows_, max(forecast_made_at_local) as last_forecast_local
from `${project}.${dataset}.station_forecasts`
group by 1, 2 order by 1;
