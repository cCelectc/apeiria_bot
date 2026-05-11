<script setup lang="ts">
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

withDefaults(defineProps<{
  subtitle?: string
  title?: string
}>(), {
  subtitle: '',
  title: '',
})
</script>

<template>
  <Card class="workbench-panel">
    <CardHeader v-if="title || subtitle || $slots.actions" class="workbench-panel__header">
      <div>
        <CardTitle v-if="title" class="workbench-panel__title">
          {{ title }}
        </CardTitle>
        <CardDescription v-if="subtitle">
          {{ subtitle }}
        </CardDescription>
      </div>
      <div v-if="$slots.actions" class="workbench-panel__actions">
        <slot name="actions" />
      </div>
    </CardHeader>
    <CardContent class="workbench-panel__content">
      <slot />
    </CardContent>
  </Card>
</template>
