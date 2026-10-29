import L from 'leaflet'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { Cpu, Flame, FireExtinguisher, WifiOff } from 'lucide-react'

import type { DeviceState } from '@/lib/format'

const cache = new Map<string, L.DivIcon>()

// Bigger pins on touch screens so they're easy to tap.
const TOUCH = window.matchMedia('(pointer: coarse)').matches
const STATION_SIZE = TOUCH ? 36 : 30
const DEVICE_SIZE = TOUCH ? 32 : 26

function svg(icon: typeof Flame, size: number) {
  return renderToStaticMarkup(createElement(icon, { size, strokeWidth: 2.25, 'aria-hidden': true }))
}

function cached(key: string, build: () => L.DivIcon) {
  let icon = cache.get(key)
  if (!icon) {
    icon = build()
    cache.set(key, icon)
  }
  return icon
}

export function stationIcon(alertCount: number, selected: boolean) {
  const badge = alertCount > 0 ? `<span class="fs-pin__badge">${alertCount > 99 ? '99+' : alertCount}</span>` : ''
  return cached(`s:${Math.min(alertCount, 100)}:${selected}`, () =>
    L.divIcon({
      className: 'fs-marker',
      html: `<div class="fs-pin fs-pin--station" data-selected="${selected}" style="position:relative;width:${STATION_SIZE}px;height:${STATION_SIZE}px">${svg(FireExtinguisher, TOUCH ? 18 : 16)}${badge}</div>`,
      iconSize: [STATION_SIZE, STATION_SIZE],
      iconAnchor: [STATION_SIZE / 2, STATION_SIZE / 2],
    }),
  )
}

const DEVICE_GLYPH: Record<DeviceState, typeof Flame> = { fire: Flame, ok: Cpu, offline: WifiOff }

export function deviceIcon(state: DeviceState, selected: boolean) {
  return cached(`d:${state}:${selected}`, () =>
    L.divIcon({
      className: 'fs-marker',
      html: `<div class="fs-pin fs-pin--device" data-state="${state}" data-selected="${selected}" style="width:${DEVICE_SIZE}px;height:${DEVICE_SIZE}px">${svg(DEVICE_GLYPH[state], TOUCH ? 16 : 14)}</div>`,
      iconSize: [DEVICE_SIZE, DEVICE_SIZE],
      iconAnchor: [DEVICE_SIZE / 2, DEVICE_SIZE / 2],
    }),
  )
}
