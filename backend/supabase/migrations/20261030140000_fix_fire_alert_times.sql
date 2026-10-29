-- ============================================================
-- Migration: 20261030140000_fix_fire_alert_times
-- Target DB: main Supabase project (config.json -> "database")
--
-- Alerts recorded live (before the fix in fire_alert_service.py)
-- have two problems:
--   * created_at is when the row was saved, several seconds after
--     the alarm, so calls could show out of order;
--   * readings of the same fire recorded at the same moment could
--     each save a call.
-- This sets every call's time to its alarm reading's time, then
-- keeps one call per fire (none within 5 minutes before it).
-- Safe to re-run.
-- ============================================================

update public.fire_alerts fa
set created_at = sr.created_at
from public.sensor_readings sr
where sr.id = fa.reading_id
  and fa.created_at <> sr.created_at;

delete from public.fire_alerts later
using public.fire_alerts earlier
where later.device_id = earlier.device_id
  and later.id <> earlier.id
  and earlier.created_at <= later.created_at
  and later.created_at - earlier.created_at < interval '5 minutes'
  -- Equal times: keep one of the two.
  and (earlier.created_at < later.created_at or earlier.id < later.id);
