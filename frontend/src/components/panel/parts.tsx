import type { ReactNode } from 'react'
import { AlertTriangle, ShieldCheck, X } from 'lucide-react'

import type { FireAlert } from '@/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatPercent } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Floating detail card: right column on desktop, bottom sheet on phones. Doesn't block the map. */
export function PanelShell({ children, onClose, label }: { children: ReactNode; onClose: () => void; label: string }) {
  return (
    <aside
      aria-label={label}
      className={cn(
        'absolute z-[1000] flex flex-col overflow-hidden rounded-xl border bg-card text-card-foreground shadow-xl',
        'inset-x-2 bottom-2 max-h-[62dvh]',
        'md:inset-x-auto md:top-4 md:right-4 md:bottom-4 md:max-h-none md:w-[420px]',
      )}
    >
      <Button
        variant="ghost"
        size="icon-sm"
        className="absolute top-3 right-3 z-10"
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
      <Badge variant="default" title="The camera image model also saw fire or smoke">
        <ShieldCheck />
        Camera confirmed {formatPercent(alert.fire_score)}
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
    <div className="space-y-3 p-5">
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
