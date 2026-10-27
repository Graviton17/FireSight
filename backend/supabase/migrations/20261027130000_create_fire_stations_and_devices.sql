-- ============================================================
-- Migration: 20261027130000_create_fire_stations_and_devices
-- Target DB: main Supabase project (config.json -> "database")
--
-- fire_stations: Gujarat fire stations, loaded from a Google Maps
--   scrape (scripts/fire_stations) or added by hand via the API.
-- devices:       where each ESP32 node is installed, so a fire
--   alarm can be matched to the nearest station.
-- nearest_fire_stations(): straight-line (haversine) distance,
--   nearest first. No PostGIS needed at this table size.
-- ============================================================

create table public.fire_stations (
  id               uuid primary key default gen_random_uuid(),
  place_id         text unique,                 -- Google place id; null for manual entries
  name             text not null check (char_length(name) between 1 and 200),
  address          text,
  city             text,
  postal_code      text,
  state            text not null default 'Gujarat',
  phone            text,
  latitude         double precision not null check (latitude between -90 and 90),
  longitude        double precision not null check (longitude between -180 and 180),
  google_maps_url  text,
  source           text not null default 'manual' check (source in ('google_maps', 'manual')),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index idx_fire_stations_lat_lng on public.fire_stations(latitude, longitude);

alter table public.fire_stations enable row level security;


create table public.devices (
  device_id   text primary key check (char_length(device_id) between 1 and 64),
  name        text,
  latitude    double precision not null check (latitude between -90 and 90),
  longitude   double precision not null check (longitude between -180 and 180),
  address     text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

alter table public.devices enable row level security;


create or replace function public.nearest_fire_stations(
  p_latitude  double precision,
  p_longitude double precision,
  p_limit     integer default 3
)
returns table (
  id               uuid,
  name             text,
  address          text,
  city             text,
  phone            text,
  latitude         double precision,
  longitude        double precision,
  google_maps_url  text,
  distance_km      double precision
)
language sql
stable
as $$
  select
    fs.id, fs.name, fs.address, fs.city, fs.phone,
    fs.latitude, fs.longitude, fs.google_maps_url,
    6371.0 * 2 * asin(sqrt(
      power(sin(radians(fs.latitude - p_latitude) / 2), 2)
      + cos(radians(p_latitude)) * cos(radians(fs.latitude))
        * power(sin(radians(fs.longitude - p_longitude) / 2), 2)
    )) as distance_km
  from public.fire_stations fs
  order by distance_km
  limit greatest(1, least(p_limit, 20));
$$;
