import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'apeiria-theme'

function readInitialTheme(): ThemeMode {
  return localStorage.getItem(STORAGE_KEY) === 'light' ? 'light' : 'dark'
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(readInitialTheme())
  const isDark = computed(() => mode.value === 'dark')

  function applyTheme() {
    document.documentElement.classList.toggle('dark', isDark.value)
    document.documentElement.style.colorScheme = isDark.value ? 'dark' : 'light'
  }

  function setTheme(nextMode: ThemeMode) {
    mode.value = nextMode
    localStorage.setItem(STORAGE_KEY, nextMode)
    applyTheme()
  }

  function toggleTheme() {
    setTheme(isDark.value ? 'light' : 'dark')
  }

  applyTheme()

  return {
    mode,
    isDark,
    applyTheme,
    setTheme,
    toggleTheme,
  }
})
