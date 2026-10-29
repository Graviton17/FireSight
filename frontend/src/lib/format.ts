import type { MapDevice } from '@/api'

// The ESP32 posts every 5 s (firmware POST_INTERVAL_MS); a minute of silence means it is down.
const OFFLINE_AFTER_MS = 60_000

export type DeviceState = 'fire' | 'ok' | 'offline'

export function deviceState(device: Pick<MapDevice, 'last_reading_at' | 'last_fire'>, now = Date.now()): DeviceState {
  if (!device.last_reading_at) return 'offline'
  if (now - new Date(device.last_reading_at).getTime() > OFFLINE_AFTER_MS) return 'offline'
  return device.last_fire ? 'fire' : 'ok'
}

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
const absolute = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' })
const short = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 31_536_000],
  ['month', 2_592_000],
  ['day', 86_400],
  ['hour', 3_600],
  ['minute', 60],
  ['second', 1],
]

export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return 'never'
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000)
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size || unit === 'second') {
      return relative.format(Math.round(seconds / size), unit)
    }
  }
  return ''
}

export const formatDateTime = (iso: string | null | undefined) => (iso ? absolute.format(new Date(iso)) : '—')
export const formatShort = (iso: string | null | undefined) => (iso ? short.format(new Date(iso)) : '—')

export const formatTemp = (t: number | null | undefined) => (t == null ? '—' : `${t.toFixed(1)} °C`)
export const formatKm = (km: number) => (km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(2)} km`)
export const formatPercent = (p: number | null | undefined) => (p == null ? '—' : `${Math.round(p * 100)}%`)

export const deviceLabel = (d: { name: string | null; device_id: string }) => d.name || d.device_id
