-- ============================================================
-- Migration: 20261030150000_fire_alert_incidents
-- Target DB: main Supabase project (config.json -> "database")
--
-- A fire alert is now an incident: live from the moment the
-- camera confirms the fire until someone presses the button on
-- the device (POST /api/v1/sensor-data/{device_id}/resolve).
-- While live, the device buzzes and the camera is not used again.
--
-- resolved_at: null = live, set = when the button was pressed.
-- Alerts recorded before this migration are closed at their own
-- time, so none of them blocks a new incident.
-- Safe to re-run.
-- ============================================================

do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'fire_alerts' and column_name = 'resolved_at'
  ) then
    alter table public.fire_alerts add column resolved_at timestamptz;
    update public.fire_alerts set resolved_at = created_at;
  end if;
end $$;

-- One live incident per device; the sensor route looks it up on every fire reading.
create index if not exists idx_fire_alerts_device_live
  on public.fire_alerts(device_id)
  where resolved_at is null;
