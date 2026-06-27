import { defineStore } from "pinia";
import { ref } from "vue";

export type Theme = "light" | "dark" | "system";

export const useUiStore = defineStore(
  "ui",
  () => {
    const theme = ref<Theme>("system");
    const sidebarCollapsed = ref(false);

    function setTheme(t: Theme) {
      theme.value = t;
    }

    function toggleSidebar() {
      sidebarCollapsed.value = !sidebarCollapsed.value;
    }

    return { theme, sidebarCollapsed, setTheme, toggleSidebar };
  },
  { persist: true },
);
