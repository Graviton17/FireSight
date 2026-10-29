import { useState, type CSSProperties, type ReactNode } from 'react'
import { AlertTriangle, ShieldCheck, X } from 'lucide-react'

import type { FireAlert } from '@/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { SHEET_HEIGHT, useLayout } from '@/hooks/useLayout'
import { formatPercent } from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * Floating detail card that leaves the map usable: a bottom sheet on phones
 * in portrait (tap the handle to expand), a docked side panel elsewhere.
 */
export function PanelShell({ children, onClose, label }: { children: ReactNode; onClose: () => void; label: string }) {
  const layout = useLayout()
  const [expanded, setExpanded] = useState(false)
  const sheet = layout.mode === 'sheet'

  const style: CSSProperties = sheet
    ? { height: `${(expanded ? SHEET_HEIGHT.expanded : SHEET_HEIGHT.collapsed) * 100}dvh` }
    : {
        top: `max(${layout.gutter}px, env(safe-area-inset-top))`,
        bottom: `max(${layout.gutter}px, env(safe-area-inset-bottom))`,
        right: `max(${layout.gutter}px, env(safe-area-inset-right))`,
        width: layout.panelWidth,
      }

  return (
    <aside
      aria-label={label}
      style={style}
      className={cn(
        'absolute z-[1000] flex flex-col overflow-hidden border bg-card text-card-foreground shadow-xl',
        sheet
          ? 'inset-x-0 bottom-0 rounded-t-2xl border-b-0 pb-[env(safe-area-inset-bottom)] transition-[height] duration-200 ease-out motion-reduce:transition-none'
          : 'rounded-xl',
      )}
    >
      {sheet && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          aria-label={expanded ? 'Shrink details' : 'Expand details'}
          aria-expanded={expanded}
          className="flex h-5 w-full shrink-0 cursor-pointer items-center justify-center focus-visible:outline-none [&:focus-visible>span]:bg-foreground"
        >
          <span className="h-1 w-10 rounded-full bg-muted-foreground/40" />
        </button>
      )}
      <Button
        variant="ghost"
        size="icon-sm"
        className={cn('absolute right-3 z-10', sheet ? 'top-6' : 'top-3')}
        onClick={onClose}
        aria-label="Close details"
      >
        <X />
      </Button>
      {children}
    </aside>
  )
}

export function Stat({ label, value, hint, className }: { label: string; value: ReactNode; hint?: string; className?: string }) {
  return (
    <div className={cn('rounded-lg border bg-background px-3 py-2', className)}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-base font-semibold tabular-nums">{value}</div>
      {hint && <div className="text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  )
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[96px_1fr] gap-2 py-1 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  )
}

export function SectionTitle({ children, count }: { children: ReactNode; count?: number }) {
  return (
    <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
      {children}
      {count != null && (
        <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">
          {count}
        </Badge>
      )}
    </h3>
  )
}

export function VerificationBadge({ alert }: { alert: Pick<FireAlert, 'verification_status' | 'fire_score'> }) {
  if (alert.verification_status === 'confirmed') {
    return (
      <Badge
        variant="default"
        title={`The camera check confirmed the fire${alert.fire_score != null ? ` (model fire score ${formatPercent(alert.fire_score)})` : ''}`}
      >
        <ShieldCheck />
        Camera confirmed
      </Badge>
    )
  }
  return (
    <Badge variant="outline" title="Camera or model was unavailable, so the alarm went out on the sensors alone">
      <AlertTriangle />
      Sensors only
    </Badge>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">{children}</p>
}

export function ErrorNote({ error }: { error: Error }) {
  return (
    <p className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
      {error.message || 'Could not reach the backend.'}
    </p>
  )
}

export function PanelSkeleton() {
  return (
    <div className="space-y-3 p-4 sm:p-5">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
      <div className="grid grid-cols-3 gap-2 pt-2">
        <Skeleton className="h-14" />
        <Skeleton className="h-14" />
        <Skeleton className="h-14" />
      </div>
      <Skeleton className="h-24" />
      <Skeleton className="h-24" />
    </div>
  )
}
