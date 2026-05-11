<script setup lang="ts">
import { Alert, AlertDescription } from '@/components/ui/alert'

withDefaults(defineProps<{
  dense?: boolean
  errorMessage?: string
  fullHeight?: boolean
  kicker?: string
  subtitle?: string
  title: string
}>(), {
  dense: false,
  errorMessage: '',
  fullHeight: false,
  kicker: '',
  subtitle: '',
})
</script>

<template>
  <section
    class="workbench-page"
    :class="{
      'workbench-page--dense': dense,
      'workbench-page--full-height': fullHeight,
    }"
  >
    <header class="workbench-page__header">
      <div class="workbench-page__heading">
        <div v-if="kicker" class="workbench-page__kicker">
          {{ kicker }}
        </div>
        <h1 class="workbench-page__title">
          {{ title }}
        </h1>
        <p v-if="subtitle" class="workbench-page__subtitle">
          {{ subtitle }}
        </p>
        <slot name="meta" />
      </div>

      <div v-if="$slots.actions" class="workbench-page__actions">
        <slot name="actions" />
      </div>
    </header>

    <slot name="before" />

    <Alert v-if="errorMessage" variant="destructive">
      <AlertDescription>{{ errorMessage }}</AlertDescription>
    </Alert>

    <slot name="alerts" />

    <main class="workbench-page__body">
      <slot />
    </main>
  </section>
</template>
