import { useCallback, useEffect, useState } from 'react'

export interface Polled<T> {
  data: T | undefined
  error: Error | undefined
  loading: boolean
  /** Fetch now (and restart the interval), e.g. when the backend says something changed. */
  refresh: () => void
}

/**
 * Runs `fetcher` now and every `intervalMs`, aborting the previous call when
 * `key` changes. Keeps the last good data while a refresh is in flight.
 * `refresh()` fetches immediately, aborting a call already in flight.
 */
export function usePolled<T>(
  key: string | null,
  fetcher: (signal: AbortSignal) => Promise<T>,
  intervalMs: number,
): Polled<T> {
  const [state, setState] = useState<{ key: string | null } & Omit<Polled<T>, 'refresh'>>({
    key,
    data: undefined,
    error: undefined,
    loading: key !== null,
  })

  const [nonce, setNonce] = useState(0)
  const refresh = useCallback(() => setNonce((n) => n + 1), [])

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
  }, [key, intervalMs, nonce])

  return { data: state.data, error: state.error, loading: state.loading, refresh }
}
