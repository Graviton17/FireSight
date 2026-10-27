-- ============================================================
-- Migration: 20261027140000_fire_stations_postgis
-- Target DB: main Supabase project (config.json -> "database")
--
-- Index-backed nearest-station search. `location` is derived
-- from latitude/longitude, so the importer and the API keep
-- writing plain lat/lng. nearest_fire_stations() keeps the same
-- signature and columns; it now walks a GiST index (KNN `<->`)
-- instead of computing the distance to every row, and measures
-- distance on the WGS84 spheroid.
-- ============================================================

create extension if not exists postgis with schema extensions;

alter table public.fire_stations
  add column location extensions.geography(Point, 4326)
  generated always as (
    extensions.st_setsrid(extensions.st_makepoint(longitude, latitude), 4326)::extensions.geography
  ) stored;

create index idx_fire_stations_location on public.fire_stations using gist (location);

-- The btree on (latitude, longitude) never helped a distance sort.
drop index if exists public.idx_fire_stations_lat_lng;


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
set search_path = public, extensions
as $$
  select
    fs.id, fs.name, fs.address, fs.city, fs.phone,
    fs.latitude, fs.longitude, fs.google_maps_url,
    st_distance(
      fs.location,
      st_setsrid(st_makepoint(p_longitude, p_latitude), 4326)::geography
    ) / 1000.0 as distance_km
  from public.fire_stations fs
  -- KNN operator: served by idx_fire_stations_location, no full scan.
  order by fs.location <-> st_setsrid(st_makepoint(p_longitude, p_latitude), 4326)::geography
  limit greatest(1, least(p_limit, 20));
$$;
