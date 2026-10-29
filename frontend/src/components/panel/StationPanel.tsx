import { useEffect } from 'react'
import { ChevronRight, Cpu, ExternalLink, FireExtinguisher, MapPin, Phone, Thermometer } from 'lucide-react'

import { api, type FireAlert } from '@/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { usePolled } from '@/hooks/usePolled'
import { formatDateTime, formatKm, formatTemp, timeAgo } from '@/lib/format'
import { Empty, ErrorNote, Field, PanelShell, PanelSkeleton, SectionTitle, Stat, VerificationBadge } from './parts'

interface Props {
  stationId: string
  onClose: () => void
  onSelectDevice: (alert: FireAlert) => void
  onAlerts: (alerts: FireAlert[]) => void
}

export function StationPanel({ stationId, onClose, onSelectDevice, onAlerts }: Props) {
  const { data, error } = usePolled(
    stationId,
    async (signal) => {
      const [station, alerts] = await Promise.all([api.station(stationId, signal), api.stationAlerts(stationId, signal)])
      return { station, alerts }
    },
    10_000,
  )

  useEffect(() => {
    if (data) onAlerts(data.alerts.items)
  }, [data, onAlerts])

  if (!data) {
    return (
      <PanelShell onClose={onClose} label="Fire station details">
        {error ? <div className="p-5 pt-12"><ErrorNote error={error} /></div> : <PanelSkeleton />}
      </PanelShell>
    )
  }

  const { station, alerts } = data
  const last = alerts.items[0]
  const devices = new Set(alerts.items.map((a) => a.device_id)).size
  const mapsUrl = station.google_maps_url ?? `https://maps.google.com/?q=${station.latitude},${station.longitude}`

  return (
    <PanelShell onClose={onClose} label="Fire station details">
      <header className="space-y-1 border-b p-5 pr-12">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <FireExtinguisher className="size-3.5" />
          Fire station
          {station.source === 'manual' && <Badge variant="outline" className="h-4 text-[10px]">added by hand</Badge>}
        </div>
        <h2 className="text-lg leading-snug font-semibold">{station.name}</h2>
        {station.city && <p className="text-sm text-muted-foreground">{station.city}{station.state ? `, ${station.state}` : ''}</p>}
        <div className="flex flex-wrap gap-2 pt-2">
          {station.phone && (
            <Button size="sm" asChild>
              <a href={`tel:${station.phone.replace(/\s+/g, '')}`}>
                <Phone /> {station.phone}
              </a>
            </Button>
          )}
          <Button size="sm" variant="outline" asChild>
            <a href={mapsUrl} target="_blank" rel="noreferrer">
              <ExternalLink /> Open in Maps
            </a>
          </Button>
        </div>
      </header>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-5 p-5">
          {error && <ErrorNote error={error} />}

          <div className="grid grid-cols-3 gap-2">
            <Stat label="Calls" value={alerts.total} />
            <Stat label="Devices" value={devices} />
            <Stat label="Last call" value={last ? timeAgo(last.created_at) : '—'} className="col-span-1" />
          </div>

          <dl>
            <Field label="Address">{station.address ?? '—'}</Field>
            <Field label="Coordinates">
              <span className="tabular-nums">{station.latitude.toFixed(5)}, {station.longitude.toFixed(5)}</span>
            </Field>
          </dl>

          <Separator />

          <section>
            <SectionTitle count={alerts.total}>Calls from devices</SectionTitle>
            {alerts.items.length === 0 ? (
              <Empty>No device has called this station yet. A call is logged when a device's alarm goes off and this is its nearest station.</Empty>
            ) : (
              <ol className="space-y-2">
                {alerts.items.map((alert) => (
                  <li key={alert.id}>
                    <AlertCard alert={alert} onSelect={() => onSelectDevice(alert)} />
                  </li>
                ))}
              </ol>
            )}
            {alerts.total > alerts.items.length && (
              <p className="mt-2 text-center text-xs text-muted-foreground">Showing the latest {alerts.items.length} of {alerts.total}.</p>
            )}
          </section>
        </div>
      </ScrollArea>
    </PanelShell>
  )
}

function AlertCard({ alert, onSelect }: { alert: FireAlert; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="group w-full rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 font-medium">
            <Cpu className="size-4 shrink-0" />
            <span className="truncate">{alert.device_name || alert.device_id}</span>
          </div>
          {alert.device_name && <div className="truncate pl-5.5 font-mono text-xs text-muted-foreground">{alert.device_id}</div>}
        </div>
        <ChevronRight className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
      </div>
      <div className="mt-2 text-sm">
        <span className="font-medium tabular-nums">{formatDateTime(alert.created_at)}</span>
        <span className="text-muted-foreground"> · {timeAgo(alert.created_at)}</span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <VerificationBadge alert={alert} />
        <Badge variant="secondary">
          <MapPin /> {formatKm(alert.distance_km)} away
        </Badge>
        <Badge variant="secondary">
          <Thermometer /> {formatTemp(alert.temperature)}
        </Badge>
      </div>
    </button>
  )
}
