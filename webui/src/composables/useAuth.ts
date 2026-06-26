import { useMutation } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

export function useLoginMutation() {
  const auth = useAuthStore()
  const router = useRouter()
  return useMutation({
    mutationFn: api.auth.login,
    onSuccess: (data) => {
      auth.setSession(data.token, data.username)
      void router.push({ name: 'dashboard' })
    },
  })
}

export function useChangePasswordMutation() {
  return useMutation({ mutationFn: api.auth.changePassword })
}
