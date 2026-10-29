import { useCallback, useMemo, useState } from 'react'
import { MapContainer, Marker, Polyline, TileLayer, ZoomControl } from 'react-leaflet'
import L, { type Map as LeafletMap, type PointTuple } from 'leaflet'
import 'leaflet/dist/leaflet.css'

import { api, type FireAlert } from '@/api'
import { MapOverlay } from '@/components/MapOverlay'
import { deviceIcon, stationIcon } from '@/components/map/icons'
import { DevicePanel } from '@/components/panel/DevicePanel'
import { StationPanel } from '@/components/panel/StationPanel'
import { SHEET_HEIGHT, useLayout, type Layout } from '@/hooks/useLayout'
import { useViewportData } from '@/hooks/useViewportData'
import { deviceState } from '@/lib/format'

// Gujarat, where the fire station directory comes from.
const START_CENTER: [number, number] = [22.6, 71.6]
const START_ZOOM = 7
const FOCUS_ZOOM = 14

// Margin around the uncovered map area, so a focused marker isn't on the edge.
const MARGIN = 24
// The overlay's title bar on phones (it shrinks to that while a sheet is open).
const OVERLAY_BAR = 64

/** Padding (px) that keeps a point out from under the detail panel and overlay. */
function uncoveredPadding(layout: Layout): { paddingTopLeft: PointTuple; paddingBottomRight: PointTuple } {
  if (layout.mode === 'sheet') {
    const sheet = Math.round(window.innerHeight * SHEET_HEIGHT.collapsed)
    return { paddingTopLeft: [MARGIN, OVERLAY_BAR + MARGIN], paddingBottomRight: [MARGIN, sheet + MARGIN] }
  }
  return {
    paddingTopLeft: [MARGIN, MARGIN],
    paddingBottomRight: [layout.panelWidth + layout.gutter + MARGIN, MARGIN],
  }
}

export type Selection = { kind: 'station'; id: string } | { kind: 'device'; id: string } | null

export default function App() {
  const [map, setMap] = useState<LeafletMap | null>(null)
  const [selection, setSelection] = useState<Selection>(null)
  const [alerts, setAlerts] = useState<FireAlert[]>([])
  const { stations, devices, truncated, loading, error } = useViewportData(map)

  const select = useCallback((next: Selection) => {
    setAlerts([])
    setSelection(next)
  }, [])

  const layout = useLayout()

  // Go to a point, landing it in the part of the map the panel doesn't cover.
  const flyTo = useCallback(
    (lat: number, lng: number) => {
      if (!map) return
      const zoom = Math.max(map.getZoom(), FOCUS_ZOOM)
      const { paddingTopLeft: [l, t], paddingBottomRight: [r, b] } = uncoveredPadding(layout)
      const size = map.getSize()
      // Shift the map centre by how far the visible area's centre is from it.
      const offset = L.point((l - r) / 2, (t - b) / 2)
      const target = map.unproject(map.project([lat, lng], zoom).subtract(offset), zoom)
      if (size.x > 0) map.flyTo(target, zoom, { duration: 0.8 })
    },
    [map, layout],
  )

  // Clicked on the map: pan only if the marker would end up under the panel.
  const reveal = useCallback(
    (lat: number, lng: number) => map?.panInside([lat, lng], uncoveredPadding(layout)),
    [map, layout],
  )

  const stationsById = useMemo(() => new Map(stations.map((s) => [s.id, s])), [stations])

  // From a station's call list: go to the device that called.
  const openDevice = useCallback(
    (alert: FireAlert) => {
      select({ kind: 'device', id: alert.device_id })
      flyTo(alert.device_latitude, alert.device_longitude)
    },
    [select, flyTo],
  )

  // From a device's trigger list: go to the station it called.
  const openStation = useCallback(
    async (alert: FireAlert) => {
      select({ kind: 'station', id: alert.fire_station_id })
      const known = stationsById.get(alert.fire_station_id)
      const station = known ?? (await api.station(alert.fire_station_id).catch(() => null))
      if (station) flyTo(station.latitude, station.longitude)
    },
    [select, flyTo, stationsById],
  )

  // Dashed lines between the selected item and the other end of its calls.
  const links = useMemo(() => {
    if (!selection) return []
    const seen = new Set<string>()
    const lines: [number, number][][] = []
    for (const a of alerts) {
      const station = stationsById.get(a.fire_station_id)
      const key = selection.kind === 'station' ? a.device_id : a.fire_station_id
      if (!station || seen.has(key)) continue
      seen.add(key)
      lines.push([
        [a.device_latitude, a.device_longitude],
        [station.latitude, station.longitude],
      ])
    }
    return lines
  }, [alerts, selection, stationsById])

  return (
    <main className="relative h-dvh w-full overflow-hidden bg-background">
      <MapContainer
        center={START_CENTER}
        zoom={START_ZOOM}
        minZoom={4}
        zoomControl={false}
        ref={setMap}
        className="z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ZoomControl position="bottomleft" />

        {links.map((positions, i) => (
          <Polyline
            key={i}
            positions={positions}
            pathOptions={{ color: '#171717', weight: 2, dashArray: '6 6', opacity: 0.75 }}
          />
        ))}

        {stations.map((s) => (
          <Marker
            key={s.id}
            position={[s.latitude, s.longitude]}
            icon={stationIcon(s.alert_count, selection?.kind === 'station' && selection.id === s.id)}
            title={s.name}
            alt={`Fire station: ${s.name}`}
            zIndexOffset={0}
            eventHandlers={{
              click: () => {
                select({ kind: 'station', id: s.id })
                reveal(s.latitude, s.longitude)
              },
            }}
          />
        ))}

        {devices.map((d) => {
          const state = deviceState(d)
          return (
            <Marker
              key={d.device_id}
              position={[d.latitude, d.longitude]}
              icon={deviceIcon(state, selection?.kind === 'device' && selection.id === d.device_id)}
              title={d.name || d.device_id}
              alt={`Device: ${d.name || d.device_id}`}
              // Devices, and burning ones most of all, sit above stations.
              zIndexOffset={state === 'fire' ? 2000 : 1000}
              eventHandlers={{
                click: () => {
                  select({ kind: 'device', id: d.device_id })
                  reveal(d.latitude, d.longitude)
                },
              }}
            />
          )
        })}
      </MapContainer>

      <MapOverlay
        stations={stations}
        devices={devices}
        truncated={truncated}
        loading={loading}
        error={error}
        panelOpen={selection !== null}
        onSelectDevice={(d) => {
          select({ kind: 'device', id: d.device_id })
          flyTo(d.latitude, d.longitude)
        }}
      />

      {selection?.kind === 'station' && (
        <StationPanel
          key={selection.id}
          stationId={selection.id}
          onClose={() => select(null)}
          onSelectDevice={openDevice}
          onAlerts={setAlerts}
        />
      )}
      {selection?.kind === 'device' && (
        <DevicePanel
          key={selection.id}
          deviceId={selection.id}
          onClose={() => select(null)}
          onSelectStation={openStation}
          onAlerts={setAlerts}
        />
      )}
    </main>
  )
}
