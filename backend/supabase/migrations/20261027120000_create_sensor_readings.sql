-- ============================================================
-- Migration: 20261027120000_create_sensor_readings
-- Target DB: main Supabase project (config.json -> "database")
--
-- One row per POST from an ESP32 fire node. The device decides
-- `fire` itself; the backend only stores it. The dashboard can
-- watch new rows over Supabase Realtime.
-- ============================================================

create table public.sensor_readings (
  id           uuid primary key default gen_random_uuid(),
  device_id    text not null check (char_length(device_id) between 1 and 64),
  smoke        smallint not null check (smoke between 0 and 4095),   -- MQ-2 raw ADC
  flame        smallint not null check (flame between 0 and 4095),   -- flame sensor raw ADC (low = flame)
  temperature  real,                                                 -- °C, null when NTC disconnected
  fire         boolean not null default false,
  created_at   timestamptz not null default now()
);

create index idx_sensor_readings_device_created
  on public.sensor_readings(device_id, created_at desc);

-- Only the backend (service_role, which bypasses RLS) writes. Add select
-- policies here when the frontend reads directly from Supabase.
alter table public.sensor_readings enable row level security;

-- Live updates in the UI
alter publication supabase_realtime add table public.sensor_readings;
