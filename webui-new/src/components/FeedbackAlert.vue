<template>
  <Alert :variant="variant">
    <AlertTriangle v-if="variant === 'destructive'" class="size-4" />
    <Info v-else class="size-4" />
    <AlertTitle v-if="title">{{ title }}</AlertTitle>
    <AlertDescription>{{ message }}</AlertDescription>
  </Alert>
</template>

<script setup lang="ts">
import { AlertTriangle, Info } from "@lucide/vue"
import Alert from "@/components/ui/alert/Alert.vue"
import AlertDescription from "@/components/ui/alert/AlertDescription.vue"
import AlertTitle from "@/components/ui/alert/AlertTitle.vue"

defineProps<{
  message: string
  title?: string
  variant?: "default" | "destructive"
}>()
</script>
