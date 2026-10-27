-- ============================================================
-- Migration: 20261028120000_add_fire_images
-- Target DB: main Supabase project (config.json -> "database")
--
-- When a device reports fire, the backend grabs a snapshot from
-- the phone (IP Webcam app), stores it in the private
-- `fire-images` bucket, and records it here. One image per
-- reading at most. The backend uploads with the service role
-- and serves signed URLs, so no storage.objects policies are
-- needed for browser access.
--
-- Object path: fire-images/{device_id}/{YYYY-MM-DD}/{reading_id}.jpg
-- Stored in fire_images.storage_path as: {device_id}/{YYYY-MM-DD}/{reading_id}.jpg
-- ============================================================

create table public.fire_images (
  id            uuid primary key default gen_random_uuid(),
  reading_id    uuid not null unique references public.sensor_readings(id) on delete cascade,
  device_id     text not null check (char_length(device_id) between 1 and 64),
  bucket        text not null default 'fire-images',
  storage_path  text not null unique check (char_length(storage_path) between 1 and 512),
  content_type  text not null default 'image/jpeg',
  size_bytes    integer not null check (size_bytes > 0),
  captured_at   timestamptz not null,
  created_at    timestamptz not null default now()
);

create index idx_fire_images_device_captured
  on public.fire_images(device_id, captured_at desc);

-- Only the backend (service_role, which bypasses RLS) writes.
alter table public.fire_images enable row level security;

-- Live updates in the UI
alter publication supabase_realtime add table public.fire_images;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'fire-images',
  'fire-images',
  false,
  5242880, -- 5 MiB
  array['image/jpeg']::text[]
)
on conflict (id) do update set
  public             = excluded.public,
  file_size_limit    = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
