import { defineStore } from "pinia";
import { ref } from "vue";

export type Theme = "light" | "dark" | "system";

export const useUiStore = defineStore(
  "ui",
  () => {
    const theme = ref<Theme>("system");

    function setTheme(t: Theme) {
      theme.value = t;
    }

    return { theme, setTheme };
  },
  { persist: true },
);
