import type { WebUIPrincipal } from '@/api/auth'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type AuthStatus =
  | 'anonymous'
  | 'restoring'
  | 'authenticated'
  | 'expired'

interface RestoreOptions {
  unauthorizedStatus?: Extract<AuthStatus, 'anonymous' | 'expired'>
}

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

  function logout(nextStatus: AuthStatus = 'anonymous') {
    clearSession(nextStatus)
  }

  function handleUnauthorized() {
    clearSession('expired')
  }

  async function initialize(options: RestoreOptions = {}) {
    if (status.value === 'authenticated' && principal.value) {
      return
    }
    if (restorePromise.value) {
      await restorePromise.value
      return
    }

    status.value = 'restoring'
    restorePromise.value = restoreCurrentUser(
      options.unauthorizedStatus ?? 'anonymous',
    )
    await restorePromise.value
  }

  async function restoreCurrentUser(
    unauthorizedStatus: Extract<AuthStatus, 'anonymous' | 'expired'>,
  ) {
    try {
      const response = await fetch('/api/auth/me', {
        credentials: 'same-origin',
      })
      if (response.status === 401) {
        clearSession(unauthorizedStatus)
        return
      }
      if (!response.ok) {
        clearSession(unauthorizedStatus)
        return
      }

      const nextPrincipal = await response.json() as WebUIPrincipal
      principal.value = nextPrincipal
      status.value = 'authenticated'
    } catch {
      clearSession(unauthorizedStatus)
    } finally {
      restorePromise.value = null
    }
  }

  async function ensureInitialized(options: RestoreOptions = {}) {
    if (status.value === 'authenticated' && principal.value) {
      return
    }
    await initialize(options)
  }

  return {
    principal,
    status,
    isReady,
    isAuthenticated,
    acceptSession,
    clearSession,
    logout,
    handleUnauthorized,
    initialize,
    ensureInitialized,
  }
})
