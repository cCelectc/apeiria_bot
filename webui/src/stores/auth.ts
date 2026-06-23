import type { WebUIPrincipal } from '@/api/auth'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type AuthStatus =
  | 'anonymous'
  | 'restoring'
  | 'authenticated'

export const useAuthStore = defineStore('auth', () => {
  const principal = ref<WebUIPrincipal | null>(null)
  const status = ref<AuthStatus>('anonymous')
  const restorePromise = ref<Promise<void> | null>(null)

  const isReady = computed(() => status.value !== 'restoring')
  const isAuthenticated = computed(() => status.value === 'authenticated')

  function acceptSession(nextPrincipal: WebUIPrincipal) {
    principal.value = nextPrincipal
    status.value = 'authenticated'
  }

  function clearSession(nextStatus: AuthStatus = 'anonymous') {
    principal.value = null
    status.value = nextStatus
    restorePromise.value = null
  }

  function handleUnauthorized() {
    clearSession('anonymous')
  }

  function logout() {
    clearSession('anonymous')
  }

  async function initialize() {
    if (status.value === 'authenticated' && principal.value) {
      return
    }
    if (restorePromise.value) {
      await restorePromise.value
      return
    }

    status.value = 'restoring'
    restorePromise.value = restoreCurrentUser()
    await restorePromise.value
  }

  async function restoreCurrentUser() {
    try {
      const response = await fetch('/api/auth/me', {
        credentials: 'same-origin',
      })
      if (response.status === 401) {
        clearSession('anonymous')
        return
      }
      if (!response.ok) {
        clearSession('anonymous')
        return
      }

      const nextPrincipal = await response.json() as WebUIPrincipal
      principal.value = nextPrincipal
      status.value = 'authenticated'
    } catch {
      clearSession('anonymous')
    } finally {
      restorePromise.value = null
    }
  }

  async function ensureInitialized() {
    if (status.value === 'authenticated' && principal.value) {
      return
    }
    await initialize()
  }

  return {
    principal,
    status,
    isReady,
    isAuthenticated,
    acceptSession,
    clearSession,
    handleUnauthorized,
    logout,
    initialize,
    ensureInitialized,
  }
})
