-- ============================================================
-- Migration: 20261028130000_device_location_source
-- Target DB: main Supabase project (config.json -> "database")
--
-- Device locations now come from the IP Webcam phone's GPS
-- automatically, or are set by hand. A manual location always
-- wins: the backend never overwrites it with a phone fix.
-- ============================================================

alter table public.devices
  add column location_source text not null default 'manual'
    check (location_source in ('manual', 'phone_gps')),
  add column location_accuracy_m real check (location_accuracy_m >= 0);  -- null for manual
