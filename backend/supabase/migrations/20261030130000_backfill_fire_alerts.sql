-- ============================================================
-- Migration: 20261030130000_backfill_fire_alerts
-- Target DB: main Supabase project (config.json -> "database")
--
-- fire_alerts only started filling when it was created, so alarms
-- from before then show no calls on the map. This rebuilds them
-- from what is already stored:
--
--   * a reading "buzzed" when the device said fire and the camera
--     model did not overrule it: fire_detected, or no detection
--     row at all (camera/model unavailable -> fail-safe buzz);
--   * one call per fire: a buzzing reading starts a new call only
--     if the device had no buzzing reading in the 5 minutes before
--     (same rule as ALERT_COOLDOWN in fire_alert_service.py);
--   * the station called is the one nearest the device's current
--     location (past locations aren't kept).
--
-- Safe to re-run: existing alerts are left alone (unique reading_id).
-- ============================================================

with buzzing as (
  select
    sr.id, sr.device_id, sr.smoke, sr.flame, sr.temperature, sr.created_at,
    fd.fire_detected, fd.fire_score,
    lag(sr.created_at) over (partition by sr.device_id order by sr.created_at) as prev_at
  from public.sensor_readings sr
  left join public.fire_detections fd on fd.reading_id = sr.id
  where sr.fire
    and coalesce(fd.fire_detected, true)
),
calls as (
  select * from buzzing
  where prev_at is null or created_at - prev_at >= interval '5 minutes'
)
insert into public.fire_alerts (
  reading_id, device_id, fire_station_id, distance_km,
  device_latitude, device_longitude, verification_status, fire_score,
  smoke, flame, temperature, created_at
)
select
  c.id, c.device_id, fs.id, fs.distance_km,
  d.latitude, d.longitude,
  case when c.fire_detected then 'confirmed' else 'unavailable' end,
  c.fire_score,
  c.smoke, c.flame, c.temperature, c.created_at
from calls c
join public.devices d on d.device_id = c.device_id
cross join lateral public.nearest_fire_stations(d.latitude, d.longitude, 1) fs
on conflict (reading_id) do nothing;
