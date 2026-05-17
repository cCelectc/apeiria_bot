<script setup lang="ts">
import { Alert, AlertDescription } from '@/components/ui/alert'

withDefaults(defineProps<{
  dense?: boolean
  embedded?: boolean
  errorMessage?: string
  fullHeight?: boolean
  kicker?: string
  subtitle?: string
  title: string
}>(), {
  dense: false,
  embedded: false,
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
      'workbench-page--embedded': embedded,
      'workbench-page--full-height': fullHeight,
    }"
  >
    <header v-if="!embedded" class="workbench-page__header">
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

    <div v-else-if="$slots.actions || $slots.meta" class="workbench-page__embedded-bar">
      <div v-if="$slots.meta" class="workbench-page__embedded-meta">
        <slot name="meta" />
      </div>
      <div v-if="$slots.actions" class="workbench-page__actions">
        <slot name="actions" />
      </div>
    </div>

    <slot name="before" />

    <Alert v-if="errorMessage" variant="destructive">
      <AlertDescription>{{ errorMessage }}</AlertDescription>
    </Alert>

    <slot name="alerts" />

    <component :is="embedded ? 'div' : 'main'" class="workbench-page__body">
      <slot />
    </component>
  </section>
</template>
