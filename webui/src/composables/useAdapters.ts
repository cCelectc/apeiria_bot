import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/lib/api'

export function useAdaptersQuery() {
  return useQuery({
    queryKey: ['adapters'],
    queryFn: () => api.adapters.list(),
  })
}

export function useAdapterMutations() {
  const qc = useQueryClient()
  const invalidate = () => qc.invalidateQueries({ queryKey: ['adapters'] })
  return {
    install: useMutation({ mutationFn: api.adapters.install, onSuccess: invalidate }),
    uninstall: useMutation({ mutationFn: api.adapters.uninstall, onSuccess: invalidate }),
    setState: useMutation({ mutationFn: api.adapters.setState, onSuccess: invalidate }),
  }
}
