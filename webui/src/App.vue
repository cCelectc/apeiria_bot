<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { Toaster } from '@/components/ui/sonner'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()

function resolveActiveTheme(): 'light' | 'dark' {
  if (ui.theme !== 'system') return ui.theme
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme() {
  document.documentElement.classList.toggle('dark', resolveActiveTheme() === 'dark')
}

onMounted(applyTheme)
watch(() => ui.theme, applyTheme)
</script>

<template>
  <RouterView />
  <Toaster position="top-right" rich-colors />
</template>
