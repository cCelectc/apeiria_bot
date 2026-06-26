import { useQuery } from '@tanstack/vue-query'
import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { api } from '@/lib/api'

export function useStorePluginsQuery(query: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ['store-plugins', toValue(query)]),
    queryFn: () => api.store.searchPlugins(toValue(query)),
  })
}

export function useStoreAdaptersQuery(query: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ['store-adapters', toValue(query)]),
    queryFn: () => api.store.searchAdapters(toValue(query)),
  })
}
