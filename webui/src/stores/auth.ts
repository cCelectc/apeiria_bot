import type { WebUIPrincipal } from '@/api/auth'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { CAP_CONTROL_PANEL } from '@/constants/access'

export type AuthStatus =
  | 'anonymous'
  | 'restoring'
  | 'authenticated'
  | 'forbidden'
  | 'expired'

export const useAuthStore = defineStore('auth', () => {
  const principal = ref<WebUIPrincipal | null>(null)
  const status = ref<AuthStatus>('anonymous')
  const restorePromise = ref<Promise<void> | null>(null)

  const isReady = computed(() => status.value !== 'restoring')
  const isAuthenticated = computed(() => status.value === 'authenticated')
  const role = computed(() => normalizeRole(principal.value?.role))
  const capabilities = computed(() => principal.value?.capabilities ?? [])
  const isOwner = computed(() => hasControlPanelAccess(principal.value))

  function acceptSession(nextPrincipal: WebUIPrincipal) {
    principal.value = nextPrincipal
    status.value = hasControlPanelAccess(nextPrincipal)
      ? 'authenticated'
      : 'forbidden'
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

  function handleForbidden() {
    clearSession('forbidden')
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
        handleUnauthorized()
        return
      }
      if (response.status === 403) {
        handleForbidden()
        return
      }
      if (!response.ok) {
        handleForbidden()
        return
      }

      const nextPrincipal = await response.json() as WebUIPrincipal
      principal.value = nextPrincipal
      status.value = hasControlPanelAccess(nextPrincipal)
        ? 'authenticated'
        : 'forbidden'
      if (status.value !== 'authenticated') {
        clearSession('forbidden')
      }
    } catch {
      handleUnauthorized()
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
    role,
    capabilities,
    isReady,
    isAuthenticated,
    isOwner,
    acceptSession,
    clearSession,
    logout,
    handleUnauthorized,
    handleForbidden,
    initialize,
    ensureInitialized,
  }
})

function hasControlPanelAccess(principal: WebUIPrincipal | null) {
  return !!principal?.capabilities?.includes(CAP_CONTROL_PANEL)
}

function normalizeRole(role: string | undefined) {
  return typeof role === 'string' ? role : ''
}
