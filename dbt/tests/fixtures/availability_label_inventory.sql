select station_id,inventory_observation_id,
    timestamp(reported) as reported_at_utc,timestamp(available) as source_available_at_utc,
    usable as is_bike_observation_usable,
    case when usable then bikes>=1 end as has_bike_observed_strict,
    bikes as bikes_available
from unnest([
    struct('S1' as station_id,'old_report' as inventory_observation_id,'2026-10-10 12:59:00+00' as reported,'2026-10-10 13:02:00+00' as available,true as usable,5 as bikes),
    struct('S1','bad_quality','2026-10-10 13:01:00+00','2026-10-10 13:02:00+00',false,5),
    struct('S1','good','2026-10-10 13:04:00+00','2026-10-10 13:05:00+00',true,3),
    struct('S1','repeat','2026-10-10 13:04:00+00','2026-10-10 13:06:00+00',true,3),
    struct('S1','late','2026-10-10 13:16:00+00','2026-10-10 13:17:00+00',true,7),
    struct('S3','unusable','2026-10-10 13:03:00+00','2026-10-10 13:04:00+00',false,2),
    struct('S4','boundary','2026-10-10 13:15:00+00','2026-10-10 13:16:00+00',true,0),
    struct('S5','half_hour_before','2026-10-10 12:59:30+00','2026-10-10 13:00:00+00',true,4),
    struct('S5','half_hour_after','2026-10-10 13:29:30+00','2026-10-10 13:30:00+00',true,2),
    struct('S6','five_minute_before','2026-10-10 12:59:30+00','2026-10-10 13:00:00+00',true,4),
    struct('S6','five_minute_after','2026-10-10 13:04:30+00','2026-10-10 13:05:00+00',true,2)
])
