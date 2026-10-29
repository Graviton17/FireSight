// Typed client for the FireSight backend (backend/app/api/v1).
// In dev, Vite proxies /api to the backend (see vite.config.ts). Set
// VITE_API_BASE_URL to call a backend on another origin instead.

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

// A backend behind free ngrok answers browsers with a warning page (no CORS
// headers) unless this header is sent. Same-origin calls don't need it.
const HEADERS: HeadersInit = BASE_URL ? { 'ngrok-skip-browser-warning': 'true' } : {}

export interface Bounds {
  min_lat: number
  min_lng: number
  max_lat: number
  max_lng: number
}

export interface BoundsResponse<T> {
  items: T[]
  truncated: boolean
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface MapFireStation {
  id: string
  name: string
  latitude: number
  longitude: number
  alert_count: number
  last_alert_at: string | null
  address: string | null
  city: string | null
  phone: string | null
  google_maps_url: string | null
}

export interface MapDevice {
  device_id: string
  latitude: number
  longitude: number
  name: string | null
  address: string | null
  location_source: 'manual' | 'phone_gps'
  location_accuracy_m: number | null
  last_reading_at: string | null
  last_fire: boolean | null
  last_smoke: number | null
  last_flame: number | null
  last_temperature: number | null
  last_alert_at: string | null
  alert_count: number
}

export interface Device {
  device_id: string
  latitude: number
  longitude: number
  name: string | null
  address: string | null
  location_source: 'manual' | 'phone_gps'
  location_accuracy_m: number | null
  created_at: string | null
  updated_at: string | null
}

export interface FireStation {
  id: string
  name: string
  latitude: number
  longitude: number
  address: string | null
  city: string | null
  postal_code: string | null
  state: string
  phone: string | null
  google_maps_url: string | null
  source: 'google_maps' | 'manual'
}

export interface FireAlert {
  id: string
  reading_id: string
  device_id: string
  fire_station_id: string
  distance_km: number
  device_latitude: number
  device_longitude: number
  verification_status: 'confirmed' | 'unavailable'
  smoke: number
  flame: number
  temperature: number | null
  fire_score: number | null
  created_at: string
  device_name: string | null
  station_name: string | null
  station_phone: string | null
}

export interface FireDetection {
  label: string
  fire_score: number
  threshold: number
  fire_detected: boolean
  inference_ms: number
}

export interface FireImage {
  id: string
  reading_id: string
  captured_at: string
  url: string | null
  detection: FireDetection | null
}

export interface SensorReading {
  id: string
  device_id: string
  smoke: number
  flame: number
  temperature: number | null
  fire: boolean
  created_at: string
  image: FireImage | null
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function get<T>(path: string, params: Record<string, string | number> = {}, signal?: AbortSignal): Promise<T> {
  const query = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))
  const url = `${BASE_URL}/api/v1${path}${query.size ? `?${query}` : ''}`
  const res = await fetch(url, { signal, headers: HEADERS })
  if (!res.ok) {
    // Backend errors are {"error": {"code", "message"}}
    let message = res.statusText
    try {
      const body = await res.json()
      message = body?.error?.message ?? message
    } catch {
      // not JSON
    }
    throw new ApiError(res.status, message)
  }
  return res.json() as Promise<T>
}

const boundsParams = (b: Bounds) => ({ ...b })

export const api = {
  stationsInBounds: (b: Bounds, signal?: AbortSignal) =>
    get<BoundsResponse<MapFireStation>>('/fire-stations/in-bounds', boundsParams(b), signal),

  devicesInBounds: (b: Bounds, signal?: AbortSignal) =>
    get<BoundsResponse<MapDevice>>('/devices/in-bounds', boundsParams(b), signal),

  station: (id: string, signal?: AbortSignal) => get<FireStation>(`/fire-stations/${id}`, {}, signal),

  stationAlerts: (id: string, signal?: AbortSignal) =>
    get<Paginated<FireAlert>>(`/fire-stations/${id}/alerts`, { page_size: 50 }, signal),

  device: (deviceId: string, signal?: AbortSignal) =>
    get<Device>(`/devices/${encodeURIComponent(deviceId)}`, {}, signal),

  deviceAlerts: (deviceId: string, signal?: AbortSignal) =>
    get<Paginated<FireAlert>>(`/devices/${encodeURIComponent(deviceId)}/alerts`, { page_size: 50 }, signal),

  deviceReadings: (deviceId: string, signal?: AbortSignal) =>
    get<Paginated<SensorReading>>(`/sensor-data/${encodeURIComponent(deviceId)}`, { page_size: 30 }, signal),

  deviceImages: (deviceId: string, signal?: AbortSignal) =>
    get<Paginated<FireImage>>(`/sensor-data/${encodeURIComponent(deviceId)}/images`, { page_size: 20 }, signal),
}
