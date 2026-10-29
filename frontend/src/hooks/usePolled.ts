import { useEffect, useState } from 'react'

export interface Polled<T> {
  data: T | undefined
  error: Error | undefined
  loading: boolean
}

/**
 * Runs `fetcher` now and every `intervalMs`, aborting the previous call when
 * `key` changes. Keeps the last good data while a refresh is in flight.
 */
export function usePolled<T>(
  key: string | null,
  fetcher: (signal: AbortSignal) => Promise<T>,
  intervalMs: number,
): Polled<T> {
  const [state, setState] = useState<{ key: string | null } & Polled<T>>({
    key,
    data: undefined,
    error: undefined,
    loading: key !== null,
  })

  // Reset when the key changes (render-time adjustment, no extra effect pass).
  if (state.key !== key) {
    setState({ key, data: undefined, error: undefined, loading: key !== null })
  }

  useEffect(() => {
    if (key === null) return
    let controller = new AbortController()
    let stopped = false

    const run = async () => {
      controller.abort()
      controller = new AbortController()
      try {
        const data = await fetcher(controller.signal)
        if (!stopped) setState({ key, data, error: undefined, loading: false })
      } catch (e) {
        if (stopped || (e instanceof DOMException && e.name === 'AbortError')) return
        setState((s) => ({ ...s, error: e as Error, loading: false }))
      }
    }

    run()
    const timer = window.setInterval(run, intervalMs)
    return () => {
      stopped = true
      controller.abort()
      window.clearInterval(timer)
    }
    // `fetcher` is expected to close over `key` only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, intervalMs])

  return { data: state.data, error: state.error, loading: state.loading }
}
