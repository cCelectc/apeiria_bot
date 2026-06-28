import { defineStore } from "pinia";
import { ref } from "vue";

export const useAuthStore = defineStore(
  "auth",
  () => {
    const token = ref<string | null>(null);
    const username = ref<string | null>(null);

    function setSession(t: string, u: string) {
      token.value = t;
      username.value = u;
    }

    function clearSession() {
      token.value = null;
      username.value = null;
    }

    return { token, username, setSession, clearSession };
  },
  {
    // Token persisted in localStorage for session survival across page refreshes.
    // Acceptable for intranet admin dashboards protected by host-level auth.
    // For public deployments, migrate to HttpOnly cookie + CSRF token flow.
    persist: true,
  },
);
