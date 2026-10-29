import { useEffect, useState } from 'react'
import type { Map as LeafletMap } from 'leaflet'

import { api, type Bounds, type MapDevice, type MapFireStation } from '@/api'
import { usePolled } from '@/hooks/usePolled'

// Live device status; stations' alert counts ride along.
const REFRESH_MS = 10_000
const MOVE_DEBOUNCE_MS = 250

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

function viewportBounds(map: LeafletMap): Bounds {
  // Fetch a margin around the screen so short pans don't show empty edges.
  const b = map.getBounds().pad(0.25)
  // Coarse rounding keeps the polling key stable for tiny moves.
  const round = (v: number) => Math.round(v * 1000) / 1000
  return {
    min_lat: round(clamp(b.getSouth(), -90, 90)),
    max_lat: round(clamp(b.getNorth(), -90, 90)),
    min_lng: round(clamp(b.getWest(), -180, 180)),
    max_lng: round(clamp(b.getEast(), -180, 180)),
  }
}

export interface ViewportData {
  stations: MapFireStation[]
  devices: MapDevice[]
  truncated: boolean
  loading: boolean
  error: Error | undefined
}

/** Stations and devices inside the map's viewport, refetched on pan/zoom and every 10 s. */
export function useViewportData(map: LeafletMap | null): ViewportData {
  const [bounds, setBounds] = useState<Bounds | null>(null)

  useEffect(() => {
    if (!map) return
    let timer: number | undefined
    // Before layout the map has no size and its bounds are a point.
    const set = () => map.getSize().x > 0 && setBounds(viewportBounds(map))
    const update = () => {
      window.clearTimeout(timer)
      timer = window.setTimeout(set, MOVE_DEBOUNCE_MS)
    }
    map.whenReady(set)
    map.on('moveend', update)
    map.on('resize', update)
    return () => {
      window.clearTimeout(timer)
      map.off('moveend', update)
      map.off('resize', update)
    }
  }, [map])

  const key = bounds ? JSON.stringify(bounds) : null
  const { data, error, loading } = usePolled(
    key,
    async (signal) => {
      const [stations, devices] = await Promise.all([
        api.stationsInBounds(bounds!, signal),
        api.devicesInBounds(bounds!, signal),
      ])
      return { stations, devices }
    },
    REFRESH_MS,
  )

  // Keep showing the previous viewport's markers until the new ones arrive.
  const [last, setLast] = useState(data)
  if (data && data !== last) setLast(data)
  const shown = data ?? last

  return {
    stations: shown?.stations.items ?? [],
    devices: shown?.devices.items ?? [],
    truncated: Boolean(shown?.stations.truncated || shown?.devices.truncated),
    loading,
    error,
  }
}
