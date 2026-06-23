import { ref, shallowRef } from "vue"

interface UseRequestOptions {
  immediate?: boolean
  staleTime?: number
}

interface UseRequestReturn<T> {
  data: ReturnType<typeof shallowRef<T | undefined>>
  loading: ReturnType<typeof ref<boolean>>
  error: ReturnType<typeof ref<string | null>>
  refresh: () => Promise<void>
  mutate: (updater: (current: T | undefined) => T) => void
}

interface StaleEntry {
  timestamp: number
  data: unknown
}

const staleCache = new Map<string, StaleEntry>()
let requestSeq = 0

export function useRequest<T>(
  key: string,
  fetcher: () => Promise<T>,
  options?: UseRequestOptions,
): UseRequestReturn<T> {
  const { immediate = true, staleTime = 0 } = options ?? {}
  const cacheKey = `req:${key}`

  const data = shallowRef<T | undefined>(undefined) as ReturnType<typeof shallowRef<T | undefined>>
  const loading = ref(false)
  const error = ref<string | null>(null)

  let currentSeq = 0

  async function execute(skipStale = false): Promise<void> {
    if (!skipStale && staleTime > 0) {
      const stale = staleCache.get(cacheKey)
      if (stale && Date.now() - stale.timestamp < staleTime) {
        if (stale.data !== undefined) {
          data.value = stale.data as T
        }
        return
      }
    }

    const seq = ++requestSeq
    currentSeq = seq
    loading.value = true
    error.value = null

    try {
      const result = await fetcher()
      if (currentSeq !== seq) return
      data.value = result
      if (staleTime > 0) {
        staleCache.set(cacheKey, { timestamp: Date.now(), data: result })
      }
    } catch (err: unknown) {
      if (currentSeq !== seq) return
      const message = err instanceof Error ? err.message : "Request failed"
      error.value = message
    } finally {
      if (currentSeq === seq) {
        loading.value = false
      }
    }
  }

  function refresh(): Promise<void> {
    return execute(true)
  }

  function mutate(updater: (current: T | undefined) => T): void {
    data.value = updater(data.value)
  }

  if (immediate) {
    execute()
  }

  return { data, loading, error, refresh, mutate }
}
