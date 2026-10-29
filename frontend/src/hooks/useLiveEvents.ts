import { useEffect, useEffectEvent } from 'react'

import { eventsUrl } from '@/api'

/** What changed on the backend (GET /api/v1/events). Refetch what you show. */
export interface LiveEvent {
  kind: 'reading' | 'alert' | 'image'
  device_id: string
}

type Listener = (event: LiveEvent) => void

// One stream for the whole page, opened while anything listens.
// EventSource reconnects on its own; polling covers the gap meanwhile.
const listeners = new Set<Listener>()
let source: EventSource | null = null

function subscribe(listener: Listener) {
  listeners.add(listener)
  if (!source) {
    source = new EventSource(eventsUrl)
    source.onmessage = (message) => {
      let event: LiveEvent
      try {
        event = JSON.parse(message.data)
      } catch {
        return
      }
      for (const l of listeners) l(event)
    }
  }
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) {
      source?.close()
      source = null
    }
  }
}

/** Calls `onEvent` for every backend change, as soon as it happens. */
export function useLiveEvents(onEvent: Listener) {
  const handle = useEffectEvent(onEvent)
  useEffect(() => subscribe(handle), [])
}
