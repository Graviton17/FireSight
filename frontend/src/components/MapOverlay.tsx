import { Cpu, FireExtinguisher, Flame, Loader2, WifiOff } from 'lucide-react'

import type { MapDevice, MapFireStation } from '@/api'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { deviceLabel, deviceState, timeAgo } from '@/lib/format'

interface Props {
  stations: MapFireStation[]
  devices: MapDevice[]
  truncated: boolean
  loading: boolean
  error: Error | undefined
  onSelectDevice: (device: MapDevice) => void
}

export function MapOverlay({ stations, devices, truncated, loading, error, onSelectDevice }: Props) {
  const burning = devices.filter((d) => deviceState(d) === 'fire')

  return (
    <div className="pointer-events-none absolute top-2 left-2 z-[1000] flex w-[calc(100%-1rem)] max-w-[300px] flex-col gap-2 md:top-4 md:left-4">
      <Card className="pointer-events-auto gap-0 p-0">
        <div className="flex items-center gap-2.5 px-4 py-3">
          <div className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Flame className="size-4" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm leading-tight font-semibold">FireSight</h1>
            <p className="text-xs text-muted-foreground">
              {stations.length} stations · {devices.length} devices in view
            </p>
          </div>
          {loading && <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="Loading" />}
        </div>

        <Separator />

        <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5 px-4 py-3 text-xs">
          <Legend icon={<FireExtinguisher className="size-3" />} className="rounded-[4px] bg-primary text-primary-foreground" label="Fire station" />
          <Legend icon={<Cpu className="size-3" />} className="border-2 border-foreground bg-background" label="Device online" />
          <Legend icon={<Flame className="size-3" />} className="bg-destructive text-white" label="Fire detected" />
          <Legend icon={<WifiOff className="size-3" />} className="border-2 border-muted-foreground bg-background text-muted-foreground" label="Device offline" />
        </ul>

        {(truncated || error) && (
          <>
            <Separator />
            <div className="space-y-1 px-4 py-2.5 text-xs">
              {error && <p className="text-destructive">Can't reach the backend: {error.message}</p>}
              {truncated && <p className="text-muted-foreground">Too many to show here. Zoom in to see them all.</p>}
            </div>
          </>
        )}
      </Card>

      {burning.length > 0 && (
        <Card className="pointer-events-auto gap-0 border-destructive/50 p-0">
          <div className="flex items-center gap-2 px-4 pt-3 pb-2 text-xs font-semibold text-destructive uppercase">
            <Flame className="size-3.5" /> Active fires
            <Badge className="ml-auto h-4 bg-destructive px-1.5 text-[10px] text-white">{burning.length}</Badge>
          </div>
          <ul className="max-h-48 overflow-y-auto pb-2">
            {burning.map((d) => (
              <li key={d.device_id}>
                <button
                  type="button"
                  onClick={() => onSelectDevice(d)}
                  className="flex w-full items-center justify-between gap-2 px-4 py-1.5 text-left text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
                >
                  <span className="truncate font-medium">{deviceLabel(d)}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(d.last_reading_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

function Legend({ icon, label, className }: { icon: React.ReactNode; label: string; className: string }) {
  return (
    <li className="flex items-center gap-2">
      <span className={`grid size-5 shrink-0 place-items-center rounded-full ${className}`}>{icon}</span>
      <span className="text-muted-foreground">{label}</span>
    </li>
  )
}
