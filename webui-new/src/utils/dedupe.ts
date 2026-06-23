const inFlight = new Map<string, Promise<unknown>>()

function requestKey(...parts: unknown[]): string {
  return JSON.stringify(parts)
}

export function dedupe<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const existing = inFlight.get(key)
  if (existing) {
    return existing as Promise<T>
  }
  const promise = fetcher()
    .then((result) => {
      inFlight.delete(key)
      return result
    })
    .catch((error) => {
      inFlight.delete(key)
      throw error
    })
  inFlight.set(key, promise)
  return promise
}

export function dedupeKey(base: string, params?: Record<string, unknown>): string {
  if (!params || Object.keys(params).length === 0) {
    return base
  }
  return `${base}:${requestKey(params)}`
}

export function clearDedupeCache(): void {
  inFlight.clear()
}
