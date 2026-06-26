import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { api } from '@/lib/api'

export function usePluginsQuery() {
  return useQuery({
    queryKey: ['plugins'],
    queryFn: () => api.plugins.list(),
  })
}

export function usePluginConfigQuery(name: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ['plugin-config', toValue(name)]),
    queryFn: () => api.plugins.config(toValue(name)),
    enabled: computed(() => Boolean(toValue(name))),
  })
}

export function usePluginMutations() {
  const qc = useQueryClient()
  const invalidate = () => qc.invalidateQueries({ queryKey: ['plugins'] })
  return {
    install: useMutation({ mutationFn: api.plugins.install, onSuccess: invalidate }),
    uninstall: useMutation({ mutationFn: api.plugins.uninstall, onSuccess: invalidate }),
    setState: useMutation({ mutationFn: api.plugins.setState, onSuccess: invalidate }),
  }
}
