import { useMutation, useQuery } from '@tanstack/vue-query'
import { api } from '@/lib/api'
import type { ConfigContract } from '@/types'

export function useConfigSchema(section: string) {
  return useQuery({
    queryKey: ['configSchema', section],
    queryFn: async () => {
      return api.config.schema(section) as Promise<ConfigContract>
    },
  })
}

export function useNonebotConfig() {
  return useQuery({
    queryKey: ['config', 'nonebot'],
    queryFn: async () => {
      const res = await api.config.get()
      return (res as Record<string, unknown>).nonebot as Record<string, unknown>
    },
  })
}

export function useApeiriaConfig() {
  return useQuery({
    queryKey: ['config', 'apeiria'],
    queryFn: async () => {
      const res = await api.config.get()
      return (res as Record<string, unknown>).apeiria as Record<string, unknown>
    },
  })
}

export function useSaveNonebotConfig() {
  return useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      await api.config.update('nonebot', data)
    },
  })
}

export function useSaveApeiriaConfig() {
  return useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      await api.config.update('apeiria', data)
    },
  })
}
