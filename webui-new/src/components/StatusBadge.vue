<template>
  <span :class="variantClasses[variant]" class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium">
    <slot />
  </span>
</template>

<script setup lang="ts">
const variantClasses: Record<string, string> = {
  success: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
  warning: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
  error: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
  info: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400",
  default: "bg-muted text-muted-foreground",
}

withDefaults(defineProps<{
  variant?: "success" | "warning" | "error" | "info" | "default"
}>(), {
  variant: "default",
})
</script>
