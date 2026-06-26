import { useQuery } from '@tanstack/vue-query'
import { api } from '@/lib/api'

export function useStatusQuery() {
  return useQuery({
    queryKey: ['status'],
    queryFn: () => api.status.get(),
    refetchInterval: 10_000,
  })
}
