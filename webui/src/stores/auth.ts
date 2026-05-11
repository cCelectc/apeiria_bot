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
  const token = ref(readToken())
  const principal = ref<WebUIPrincipal | null>(readPrincipal())
  const status = ref<AuthStatus>(token.value ? 'restoring' : 'anonymous')
  const restorePromise = ref<Promise<void> | null>(null)

  const isReady = computed(() => status.value !== 'restoring')
  const isAuthenticated = computed(() => status.value === 'authenticated')
  const role = computed(() => normalizeRole(principal.value?.role))
  const capabilities = computed(() => principal.value?.capabilities ?? [])
  const isOwner = computed(() => hasControlPanelAccess(principal.value))

  function acceptSession(nextToken: string, nextPrincipal: WebUIPrincipal) {
    token.value = nextToken
    principal.value = nextPrincipal
    persistSession(nextToken, nextPrincipal)
    status.value = hasControlPanelAccess(nextPrincipal)
      ? 'authenticated'
      : 'forbidden'
  }

  function clearSession(nextStatus: AuthStatus = 'anonymous') {
    token.value = ''
    principal.value = null
    status.value = nextStatus
    restorePromise.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('apeiria-principal')
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
    if (!token.value) {
      status.value = 'anonymous'
      return
    }
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
    const currentToken = token.value
    if (!currentToken) {
      status.value = 'anonymous'
      return
    }

    try {
      const response = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${currentToken}` },
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
      persistPrincipal(nextPrincipal)
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
    token,
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

function persistPrincipal(principal: WebUIPrincipal) {
  localStorage.setItem('apeiria-principal', JSON.stringify(principal))
}

function persistSession(token: string, principal: WebUIPrincipal) {
  localStorage.setItem('token', token)
  persistPrincipal(principal)
}

function readToken() {
  return localStorage.getItem('token') || ''
}

function readPrincipal(): WebUIPrincipal | null {
  const raw = localStorage.getItem('apeiria-principal')
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw) as WebUIPrincipal
  } catch {
    localStorage.removeItem('apeiria-principal')
    return null
  }
}
