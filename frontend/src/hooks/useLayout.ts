import { useSyncExternalStore } from 'react'

/**
 * How the detail panel fits the screen.
 *
 * - `sheet`: phones in portrait (and narrow windows). Panel slides up from the
 *   bottom; the overlay shrinks to its title bar while it is open.
 * - `side`:  everything else, including phones in landscape. Panel docks to
 *   the right; its width grows with the screen.
 */
export interface Layout {
  mode: 'sheet' | 'side'
  /** Short landscape screen (phone on its side): tighter gutters, overlay starts collapsed. */
  short: boolean
  /** Side panel width in px (0 for `sheet`). */
  panelWidth: number
  /** Gap between the screen edge and floating cards, px. */
  gutter: number
}

function compute(): Layout {
  const w = window.innerWidth
  const h = window.innerHeight
  const short = h <= 500 && w > h
  const gutter = w >= 768 && !short ? 16 : 8
  if (w < 768 && !short) return { mode: 'sheet', short, panelWidth: 0, gutter }
  const panelWidth = short && w < 768 ? Math.min(340, Math.round(w * 0.58)) : w >= 1536 ? 460 : w >= 1024 ? 420 : 380
  return { mode: 'side', short, panelWidth, gutter }
}

let current = compute()
const listeners = new Set<() => void>()

function onResize() {
  const next = compute()
  if (
    next.mode !== current.mode ||
    next.short !== current.short ||
    next.panelWidth !== current.panelWidth ||
    next.gutter !== current.gutter
  ) {
    current = next
    listeners.forEach((l) => l())
  }
}

function subscribe(listener: () => void) {
  if (listeners.size === 0) window.addEventListener('resize', onResize)
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) window.removeEventListener('resize', onResize)
  }
}

export const getLayout = () => current

export function useLayout(): Layout {
  return useSyncExternalStore(subscribe, getLayout)
}

/** Share of the screen height the bottom sheet takes, collapsed and expanded. */
export const SHEET_HEIGHT = { collapsed: 0.5, expanded: 0.88 }
