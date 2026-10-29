import { useState } from 'react'
import { ChevronDown, Cpu, FireExtinguisher, Flame, Loader2, WifiOff } from 'lucide-react'

import type { MapDevice, MapFireStation } from '@/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useLayout } from '@/hooks/useLayout'
import { deviceLabel, deviceState, timeAgo } from '@/lib/format'
import { cn } from '@/lib/utils'

interface Props {
  stations: MapFireStation[]
  devices: MapDevice[]
  truncated: boolean
  loading: boolean
  error: Error | undefined
  panelOpen: boolean
  onSelectDevice: (device: MapDevice) => void
}

export function MapOverlay({ stations, devices, truncated, loading, error, panelOpen, onSelectDevice }: Props) {
  const layout = useLayout()
  // Phones start with just the title bar; the legend is a tap away.
  const [legendOpen, setLegendOpen] = useState(() => layout.mode === 'side' && !layout.short)
  const burning = devices.filter((d) => deviceState(d) === 'fire')

  // With a panel open on a phone (sheet, or side panel on a short landscape
  // screen) there's little map left: keep only the title bar.
  const minimal = panelOpen && (layout.mode === 'sheet' || layout.short)
  const showFires = burning.length > 0 && !minimal

  return (
    <div
      className={cn(
        'pointer-events-none absolute z-[1000] flex flex-col gap-2',
        layout.short ? 'w-[220px]' : 'w-[calc(100%-1rem)] max-w-[300px]',
      )}
      style={{
        top: `max(${layout.gutter}px, env(safe-area-inset-top))`,
        left: `max(${layout.gutter}px, env(safe-area-inset-left))`,
      }}
    >
      <Card className="pointer-events-auto gap-0 py-0">
        <div className={cn('flex items-center gap-2.5', layout.short ? 'px-3 py-2' : 'px-4 py-3')}>
          <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Flame className="size-4" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm leading-tight font-semibold">FireSight</h1>
            <p className="truncate text-xs text-muted-foreground">
              {stations.length} stations · {devices.length} devices
              {!layout.short && <span className="hidden sm:inline"> in view</span>}
            </p>
          </div>
          {loading && <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" aria-label="Loading" />}
          {burning.length > 0 && !showFires && (
            <Badge className="shrink-0 bg-destructive text-white" title="Devices reporting fire">
              <Flame /> {burning.length}
            </Badge>
          )}
          {!minimal && (
            <Button
              variant="ghost"
              size="icon-sm"
              className="shrink-0"
              onClick={() => setLegendOpen((o) => !o)}
              aria-expanded={legendOpen}
              aria-label={legendOpen ? 'Hide legend' : 'Show legend'}
            >
              <ChevronDown className={cn('transition-transform', legendOpen && 'rotate-180')} />
            </Button>
          )}
        </div>

        {legendOpen && !minimal && (
          <>
            <Separator />
            <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5 px-4 py-3 text-xs">
              <Legend icon={<FireExtinguisher className="size-3" />} className="rounded-[4px] bg-primary text-primary-foreground" label="Fire station" />
              <Legend icon={<Cpu className="size-3" />} className="border-2 border-foreground bg-background" label="Device online" />
              <Legend icon={<Flame className="size-3" />} className="bg-destructive text-white" label="Fire detected" />
              <Legend icon={<WifiOff className="size-3" />} className="border-2 border-muted-foreground bg-background text-muted-foreground" label="Device offline" />
            </ul>
          </>
        )}

        {(truncated || error) && !minimal && (
          <>
            <Separator />
            <div className="space-y-1 px-4 py-2.5 text-xs">
              {error && <p className="text-destructive">Can't reach the backend: {error.message}</p>}
              {truncated && <p className="text-muted-foreground">Too many to show here. Zoom in to see them all.</p>}
            </div>
          </>
        )}
      </Card>

      {showFires && (
        <Card className="pointer-events-auto gap-0 border-destructive/50 py-0">
          <div className="flex items-center gap-2 px-4 pt-3 pb-2 text-xs font-semibold text-destructive uppercase">
            <Flame className="size-3.5" /> Active fires
            <Badge className="ml-auto h-4 bg-destructive px-1.5 text-[10px] text-white">{burning.length}</Badge>
          </div>
          <ul className={cn('overflow-y-auto pb-2', layout.short ? 'max-h-24' : 'max-h-48')}>
            {burning.map((d) => (
              <li key={d.device_id}>
                <button
                  type="button"
                  onClick={() => onSelectDevice(d)}
                  className="flex min-h-10 w-full items-center justify-between gap-2 px-4 py-1.5 text-left text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
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
