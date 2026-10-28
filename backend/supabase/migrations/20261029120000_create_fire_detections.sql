-- ============================================================
-- Migration: 20261029120000_create_fire_detections
-- Target DB: main Supabase project (config.json -> "database")
--
-- Second verification: when a device reports fire, the backend
-- runs an image classifier on the phone snapshot and tells the
-- ESP32 whether to buzz. One detection per stored image; only
-- written when the model actually ran.
-- ============================================================

create table public.fire_detections (
  id             uuid primary key default gen_random_uuid(),
  image_id       uuid not null unique references public.fire_images(id) on delete cascade,
  reading_id     uuid not null unique references public.sensor_readings(id) on delete cascade,
  device_id      text not null check (char_length(device_id) between 1 and 64),
  model          text not null,                    -- Hugging Face model id
  label          text not null,                    -- top class, e.g. 'Fire', 'None'
  fire_score     real not null check (fire_score between 0 and 1),  -- sum of fire-label probabilities
  threshold      real not null check (threshold between 0 and 1),   -- threshold in force at the time
  fire_detected  boolean not null,                 -- fire_score >= threshold
  scores         jsonb not null,                   -- every label -> probability
  inference_ms   integer not null check (inference_ms >= 0),
  created_at     timestamptz not null default now()
);

create index idx_fire_detections_device_created
  on public.fire_detections(device_id, created_at desc);

-- Only the backend (service_role, which bypasses RLS) writes.
alter table public.fire_detections enable row level security;

-- Live updates in the UI
alter publication supabase_realtime add table public.fire_detections;
