import { useEffect } from 'react'
import { ChevronRight, Cpu, ExternalLink, FireExtinguisher, Flame, Phone, Thermometer, Wind } from 'lucide-react'

import { ApiError, api, type FireAlert, type FireImage, type SensorReading } from '@/api'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { usePolled } from '@/hooks/usePolled'
import { deviceState, formatDateTime, formatKm, formatPercent, formatShort, formatTemp, timeAgo } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Empty, ErrorNote, Field, PanelShell, PanelSkeleton, SectionTitle, Stat, VerificationBadge } from './parts'

interface Props {
  deviceId: string
  onClose: () => void
  onSelectStation: (alert: FireAlert) => void
  onAlerts: (alerts: FireAlert[]) => void
}

// The device posts every 5 s; refresh a bit slower than that.
const REFRESH_MS = 5_000

export function DevicePanel({ deviceId, onClose, onSelectStation, onAlerts }: Props) {
  const { data, error } = usePolled(
    deviceId,
    async (signal) => {
      const [device, readings, alerts, images] = await Promise.all([
        // 404 = no registered location; still show its readings.
        api.device(deviceId, signal).catch((e) => {
          if (e instanceof ApiError && e.status === 404) return null
          throw e
        }),
        api.deviceReadings(deviceId, signal),
        api.deviceAlerts(deviceId, signal),
        api.deviceImages(deviceId, signal),
      ])
      return { device, readings, alerts, images }
    },
    REFRESH_MS,
  )

  useEffect(() => {
    if (data) onAlerts(data.alerts.items)
  }, [data, onAlerts])

  if (!data) {
    return (
      <PanelShell onClose={onClose} label="Device details">
        {error ? <div className="p-5 pt-12"><ErrorNote error={error} /></div> : <PanelSkeleton />}
      </PanelShell>
    )
  }

  const { device, readings, alerts, images } = data
  const latest = readings.items[0]
  const state = deviceState({ last_reading_at: latest?.created_at ?? null, last_fire: latest?.fire ?? null })
  const imagesByReading = new Map(images.items.map((img) => [img.reading_id, img]))

  return (
    <PanelShell onClose={onClose} label="Device details">
      <header className="space-y-1 border-b p-5 pr-12">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Cpu className="size-3.5" />
          Device
        </div>
        <h2 className="text-lg leading-snug font-semibold">{device?.name || deviceId}</h2>
        {device?.name && <p className="font-mono text-xs text-muted-foreground">{deviceId}</p>}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <StateBadge state={state} />
          <span className="text-xs text-muted-foreground">Last seen {timeAgo(latest?.created_at)}</span>
        </div>
      </header>

      <Tabs defaultValue="live" className="min-h-0 flex-1 gap-0">
        <div className="border-b px-5 py-2">
          <TabsList className="w-full">
            <TabsTrigger value="live">Live</TabsTrigger>
            <TabsTrigger value="log">Log</TabsTrigger>
            <TabsTrigger value="triggers">
              Triggers
              {alerts.total > 0 && <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">{alerts.total}</Badge>}
            </TabsTrigger>
          </TabsList>
        </div>

        <ScrollArea className="min-h-0 flex-1">
          <div className="p-5">
            {error && <div className="mb-4"><ErrorNote error={error} /></div>}

            <TabsContent value="live" className="space-y-5">
              <section>
                <SectionTitle>Current reading</SectionTitle>
                {latest ? (
                  <>
                    <div className="grid grid-cols-3 gap-2">
                      <Stat label="Smoke" value={latest.smoke} hint="MQ-2, 0–4095" />
                      <Stat label="Flame" value={latest.flame} hint="lower = flame" />
                      <Stat label="Temp" value={formatTemp(latest.temperature)} />
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {formatDateTime(latest.created_at)} · sensors say <strong className="text-foreground">{latest.fire ? 'FIRE' : 'no fire'}</strong>
                    </p>
                    {latest.image && <Snapshot image={latest.image} className="mt-3" />}
                  </>
                ) : (
                  <Empty>This device hasn't sent any readings yet.</Empty>
                )}
              </section>

              <section>
                <SectionTitle>Location</SectionTitle>
                {device ? (
                  <dl>
                    <Field label="Address">{device.address ?? '—'}</Field>
                    <Field label="Coordinates">
                      <a
                        className="inline-flex items-center gap-1 tabular-nums underline-offset-4 hover:underline"
                        href={`https://maps.google.com/?q=${device.latitude},${device.longitude}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {device.latitude.toFixed(5)}, {device.longitude.toFixed(5)} <ExternalLink className="size-3" />
                      </a>
                    </Field>
                    <Field label="Source">
                      {device.location_source === 'phone_gps'
                        ? `Phone GPS${device.location_accuracy_m != null ? ` (±${Math.round(device.location_accuracy_m)} m)` : ''}`
                        : 'Pinned by hand'}
                    </Field>
                    <Field label="Updated">{formatDateTime(device.updated_at)}</Field>
                  </dl>
                ) : (
                  <Empty>No location registered for this device.</Empty>
                )}
              </section>

              <section>
                <SectionTitle>Last trigger</SectionTitle>
                {alerts.items[0] ? (
                  <TriggerCard alert={alerts.items[0]} image={imagesByReading.get(alerts.items[0].reading_id)} onSelect={onSelectStation} />
                ) : (
                  <Empty>No alarm from this device has called a station.</Empty>
                )}
              </section>
            </TabsContent>

            <TabsContent value="log">
              <SectionTitle count={readings.total}>Reading log</SectionTitle>
              {readings.items.length === 0 ? <Empty>No readings yet.</Empty> : <ReadingTable readings={readings.items} />}
              {readings.total > readings.items.length && (
                <p className="mt-2 text-center text-xs text-muted-foreground">Latest {readings.items.length} of {readings.total.toLocaleString()} readings.</p>
              )}
            </TabsContent>

            <TabsContent value="triggers" className="space-y-5">
              <section>
                <SectionTitle count={alerts.total}>Alarms that called a station</SectionTitle>
                {alerts.items.length === 0 ? (
                  <Empty>None yet.</Empty>
                ) : (
                  <ol className="space-y-2">
                    {alerts.items.map((a) => (
                      <li key={a.id}>
                        <TriggerCard alert={a} image={imagesByReading.get(a.reading_id)} onSelect={onSelectStation} />
                      </li>
                    ))}
                  </ol>
                )}
              </section>

              <RejectedSnapshots images={images.items} alertReadingIds={new Set(alerts.items.map((a) => a.reading_id))} />
            </TabsContent>
          </div>
        </ScrollArea>
      </Tabs>
    </PanelShell>
  )
}

function StateBadge({ state }: { state: ReturnType<typeof deviceState> }) {
  if (state === 'fire') {
    return (
      <Badge className="bg-destructive text-white">
        <Flame /> Fire detected
      </Badge>
    )
  }
  if (state === 'ok') return <Badge>Online</Badge>
  return <Badge variant="outline">Offline</Badge>
}

function ReadingTable({ readings }: { readings: SensorReading[] }) {
  return (
    <div className="overflow-hidden rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Time</TableHead>
            <TableHead className="text-right">Smoke</TableHead>
            <TableHead className="text-right">Flame</TableHead>
            <TableHead className="text-right">Temp</TableHead>
            <TableHead className="text-right">Fire</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {readings.map((r) => (
            <TableRow key={r.id} className={cn(r.fire && 'bg-destructive/5 font-medium')}>
              <TableCell className="text-xs tabular-nums">{formatShort(r.created_at)}</TableCell>
              <TableCell className="text-right tabular-nums">{r.smoke}</TableCell>
              <TableCell className="text-right tabular-nums">{r.flame}</TableCell>
              <TableCell className="text-right tabular-nums">{r.temperature == null ? '—' : r.temperature.toFixed(1)}</TableCell>
              <TableCell className="text-right">
                {r.fire ? <Flame className="ml-auto size-4 text-destructive" aria-label="fire" /> : <span className="text-muted-foreground">–</span>}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function TriggerCard({ alert, image, onSelect }: { alert: FireAlert; image?: FireImage; onSelect: (a: FireAlert) => void }) {
  return (
    <div className="rounded-lg border bg-background p-3">
      <div className="text-sm">
        <span className="font-medium tabular-nums">{formatDateTime(alert.created_at)}</span>
        <span className="text-muted-foreground"> · {timeAgo(alert.created_at)}</span>
      </div>

      <button
        type="button"
        onClick={() => onSelect(alert)}
        className="group mt-2 flex w-full items-center gap-2 rounded-md border px-2.5 py-2 text-left transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <FireExtinguisher className="size-4 shrink-0" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{alert.station_name ?? 'Unknown station'}</span>
          <span className="block text-xs text-muted-foreground">Called · {formatKm(alert.distance_km)} away</span>
        </span>
        <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
      </button>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <VerificationBadge alert={alert} />
        {alert.station_phone && (
          <Badge variant="outline" asChild>
            <a href={`tel:${alert.station_phone.replace(/\s+/g, '')}`}>
              <Phone /> {alert.station_phone}
            </a>
          </Badge>
        )}
      </div>

      <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
        <span className="flex items-center gap-1"><Wind className="size-3.5 text-muted-foreground" /> {alert.smoke}</span>
        <span className="flex items-center gap-1"><Flame className="size-3.5 text-muted-foreground" /> {alert.flame}</span>
        <span className="flex items-center gap-1"><Thermometer className="size-3.5 text-muted-foreground" /> {formatTemp(alert.temperature)}</span>
      </div>

      {image && <Snapshot image={image} className="mt-3" />}
    </div>
  )
}

function Snapshot({ image, className }: { image: FireImage; className?: string }) {
  if (!image.url) return null
  const d = image.detection
  return (
    <figure className={cn('overflow-hidden rounded-lg border', className)}>
      <a href={image.url} target="_blank" rel="noreferrer">
        <img src={image.url} alt={`Camera snapshot at ${formatDateTime(image.captured_at)}`} className="aspect-video w-full bg-muted object-cover" loading="lazy" />
      </a>
      <figcaption className="flex items-center justify-between gap-2 px-2.5 py-1.5 text-xs text-muted-foreground">
        <span>{formatShort(image.captured_at)}</span>
        {d ? (
          <span>
            Model: <strong className="text-foreground">{d.label}</strong> · fire {formatPercent(d.fire_score)}
          </span>
        ) : (
          <span>Model didn't run</span>
        )}
      </figcaption>
    </figure>
  )
}

/** Fire reports the camera model overruled: no alarm, no station called. */
function RejectedSnapshots({ images, alertReadingIds }: { images: FireImage[]; alertReadingIds: Set<string> }) {
  const rejected = images.filter((img) => !alertReadingIds.has(img.reading_id) && img.detection && !img.detection.fire_detected)
  if (rejected.length === 0) return null
  return (
    <section>
      <SectionTitle count={rejected.length}>False alarms (camera said no fire)</SectionTitle>
      <div className="grid grid-cols-2 gap-2">
        {rejected.map((img) => (
          <Snapshot key={img.id} image={img} />
        ))}
      </div>
    </section>
  )
}
