import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { api } from '@/lib/api'
import type { ConfigContract } from '@/types'

export function usePluginsQuery() {
  return useQuery({
    queryKey: ['plugins'],
    queryFn: () => api.plugins.list(),
  })
}

export function usePluginConfigQuery(name: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ['plugin-config', toValue(name)]),
    queryFn: async () => {
      const res = await api.plugins.config(toValue(name))
      return {
        schema: res as ConfigContract,
        values: res.values || {},
      }
    },
    enabled: computed(() => Boolean(toValue(name))),
  })
}

export function useSavePluginConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { name: string; data: Record<string, unknown> }) => {
      await api.config.update('plugins', { [vars.name]: vars.data })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['plugin-config'] })
    },
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
