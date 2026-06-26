import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/lib/api'

export function useConfigQuery() {
  return useQuery({
    queryKey: ['config'],
    queryFn: () => api.config.get(),
  })
}

export function useConfigMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { section: string; data: Record<string, unknown> }) =>
      api.config.update(vars.section, vars.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config'] }),
  })
}
