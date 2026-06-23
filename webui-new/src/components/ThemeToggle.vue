<template>
  <Button variant="ghost" size="icon" @click="theme.toggleTheme()">
    <Sun v-if="theme.isDark" class="size-4" />
    <Moon v-else class="size-4" />
    <span class="sr-only">Toggle theme</span>
  </Button>
</template>

<script setup lang="ts">
import { Sun, Moon } from "@lucide/vue"
import Button from "@/components/ui/button/Button.vue"
import { useThemeStore } from "@/stores/theme"

const theme = useThemeStore()
</script>
