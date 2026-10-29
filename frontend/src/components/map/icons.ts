import L from 'leaflet'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { Cpu, Flame, FireExtinguisher, WifiOff } from 'lucide-react'

import type { DeviceState } from '@/lib/format'

const cache = new Map<string, L.DivIcon>()

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
      html: `<div class="fs-pin fs-pin--station" data-selected="${selected}" style="position:relative">${svg(FireExtinguisher, 16)}${badge}</div>`,
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    }),
  )
}

const DEVICE_GLYPH: Record<DeviceState, typeof Flame> = { fire: Flame, ok: Cpu, offline: WifiOff }

export function deviceIcon(state: DeviceState, selected: boolean) {
  return cached(`d:${state}:${selected}`, () =>
    L.divIcon({
      className: 'fs-marker',
      html: `<div class="fs-pin fs-pin--device" data-state="${state}" data-selected="${selected}">${svg(DEVICE_GLYPH[state], 14)}</div>`,
      iconSize: [26, 26],
      iconAnchor: [13, 13],
    }),
  )
}
