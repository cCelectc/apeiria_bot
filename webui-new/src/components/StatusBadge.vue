<template>
  <Badge :variant="variantMap[variant]">
    <slot />
  </Badge>
</template>

<script setup lang="ts">
import Badge from "@/components/ui/badge/Badge.vue"

const variantMap: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  success: "default",
  warning: "secondary",
  error: "destructive",
  info: "outline",
  default: "outline",
}

withDefaults(defineProps<{
  variant?: "success" | "warning" | "error" | "info" | "default"
}>(), {
  variant: "default",
})
</script>
