import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { STORAGE_KEYS } from '@/constants'

export type ThemeMode = 'light' | 'dark'

function readInitialTheme(): ThemeMode {
  return localStorage.getItem(STORAGE_KEYS.theme) === 'light' ? 'light' : 'dark'
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
    localStorage.setItem(STORAGE_KEYS.theme, nextMode)
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
