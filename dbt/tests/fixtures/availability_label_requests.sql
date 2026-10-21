select concat('P',cast(n as string)) as prediction_id,concat('S',cast(n as string)) as station_id,
    timestamp('2026-10-10 12:00:00+00') as prediction_at_utc,
    timestamp('2026-10-10 13:00:00+00') as target_at_utc,
    60 as horizon_minutes,15 as label_tolerance_minutes
from unnest([1,2,3,4]) as n
