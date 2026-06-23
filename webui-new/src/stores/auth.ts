import { defineStore } from "pinia"
import { computed, ref } from "vue"

export interface WebUIPrincipal {
  id: string
  username: string
}

export type AuthStatus =
  | "anonymous"
  | "restoring"
  | "authenticated"
  | "expired"

export const useAuthStore = defineStore("auth", () => {
  const principal = ref<WebUIPrincipal | null>(null)
  const status = ref<AuthStatus>("anonymous")
  const restorePromise = ref<Promise<void> | null>(null)

  const isReady = computed(() => status.value !== "restoring")
  const isAuthenticated = computed(() => status.value === "authenticated")

  function acceptSession(next: WebUIPrincipal) {
    principal.value = next
    status.value = "authenticated"
  }

  function clearSession(nextStatus: AuthStatus = "anonymous") {
    principal.value = null
    status.value = nextStatus
    restorePromise.value = null
  }

  async function initialize(unauthorizedStatus: AuthStatus = "anonymous") {
    if (status.value === "authenticated" && principal.value) return
    if (restorePromise.value) {
      await restorePromise.value
      return
    }

    status.value = "restoring"
    restorePromise.value = fetch("/api/auth/me", { credentials: "same-origin" })
      .then(async (res) => {
        if (res.status === 401 || !res.ok) {
          clearSession(unauthorizedStatus)
          return
        }
        principal.value = await res.json()
        status.value = "authenticated"
      })
      .catch(() => clearSession(unauthorizedStatus))
      .finally(() => { restorePromise.value = null })
    await restorePromise.value
  }

  async function ensureInitialized(unauthorizedStatus: AuthStatus = "anonymous") {
    if (status.value === "authenticated" && principal.value) return
    await initialize(unauthorizedStatus)
  }

  return {
    principal,
    status,
    isReady,
    isAuthenticated,
    acceptSession,
    clearSession,
    initialize,
    ensureInitialized,
  }
})
