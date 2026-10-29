-- ============================================================
-- Migration: 20261030120000_fire_alerts_and_map
-- Target DB: main Supabase project (config.json -> "database")
--
-- fire_alerts:  one row per alarm that buzzed, recording which
--   device called which (nearest) fire station, when, and what
--   the image model said. The map's station popup lists these.
-- fire_stations_in_bounds(): stations inside the map viewport.
-- devices_in_bounds(): devices inside the viewport with their
--   latest reading and last alert, in one round trip.
-- ============================================================

create table public.fire_alerts (
  id                   uuid primary key default gen_random_uuid(),
  reading_id           uuid not null unique references public.sensor_readings(id) on delete cascade,
  device_id            text not null references public.devices(device_id) on delete cascade,
  fire_station_id      uuid not null references public.fire_stations(id) on delete cascade,
  distance_km          double precision not null check (distance_km >= 0),  -- straight-line
  device_latitude      double precision not null,   -- where the device was at alarm time
  device_longitude     double precision not null,
  verification_status  text not null check (verification_status in ('confirmed', 'unavailable')),
  fire_score           real check (fire_score between 0 and 1),            -- null when unavailable
  smoke                smallint not null,
  flame                smallint not null,
  temperature          real,
  created_at           timestamptz not null default now()
);

create index idx_fire_alerts_station_created
  on public.fire_alerts(fire_station_id, created_at desc);
create index idx_fire_alerts_device_created
  on public.fire_alerts(device_id, created_at desc);

-- Only the backend (service_role, which bypasses RLS) writes.
alter table public.fire_alerts enable row level security;

-- Live updates in the UI
alter publication supabase_realtime add table public.fire_alerts;


create or replace function public.fire_stations_in_bounds(
  p_min_lat double precision,
  p_min_lng double precision,
  p_max_lat double precision,
  p_max_lng double precision,
  p_limit   integer default 500
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
  alert_count      bigint,
  last_alert_at    timestamptz
)
language sql
stable
set search_path = public, extensions
as $$
  select
    fs.id, fs.name, fs.address, fs.city, fs.phone,
    fs.latitude, fs.longitude, fs.google_maps_url,
    coalesce(a.alert_count, 0), a.last_alert_at
  from public.fire_stations fs
  left join lateral (
    select count(*) as alert_count, max(fa.created_at) as last_alert_at
    from public.fire_alerts fa
    where fa.fire_station_id = fs.id
  ) a on true
  -- Served by idx_fire_stations_location. A planar box is fine at viewport scale.
  where fs.location && st_makeenvelope(p_min_lng, p_min_lat, p_max_lng, p_max_lat, 4326)::geography
    and fs.latitude between p_min_lat and p_max_lat
    and fs.longitude between p_min_lng and p_max_lng
  order by a.last_alert_at desc nulls last, fs.name
  limit greatest(1, least(p_limit, 2000));
$$;


create or replace function public.devices_in_bounds(
  p_min_lat double precision,
  p_min_lng double precision,
  p_max_lat double precision,
  p_max_lng double precision,
  p_limit   integer default 500
)
returns table (
  device_id            text,
  name                 text,
  address              text,
  latitude             double precision,
  longitude            double precision,
  location_source      text,
  location_accuracy_m  real,
  last_reading_at      timestamptz,
  last_fire            boolean,
  last_smoke           smallint,
  last_flame           smallint,
  last_temperature     real,
  last_alert_at        timestamptz,
  alert_count          bigint
)
language sql
stable
as $$
  select
    d.device_id, d.name, d.address, d.latitude, d.longitude,
    d.location_source, d.location_accuracy_m,
    r.created_at, r.fire, r.smoke, r.flame, r.temperature,
    a.last_alert_at, coalesce(a.alert_count, 0)
  from public.devices d
  left join lateral (
    select sr.created_at, sr.fire, sr.smoke, sr.flame, sr.temperature
    from public.sensor_readings sr
    where sr.device_id = d.device_id
    order by sr.created_at desc
    limit 1
  ) r on true
  left join lateral (
    select count(*) as alert_count, max(fa.created_at) as last_alert_at
    from public.fire_alerts fa
    where fa.device_id = d.device_id
  ) a on true
  where d.latitude between p_min_lat and p_max_lat
    and d.longitude between p_min_lng and p_max_lng
  order by d.device_id
  limit greatest(1, least(p_limit, 2000));
$$;
