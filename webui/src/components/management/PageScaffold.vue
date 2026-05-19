<script setup lang="ts">
import FeedbackAlert from './FeedbackAlert.vue'

withDefaults(defineProps<{
  ariaBusy?: boolean
  dense?: boolean
  embedded?: boolean
  errorMessage?: string
  fullHeight?: boolean
  kicker?: string
  retryLabel?: string
  subtitle?: string
  title: string
}>(), {
  ariaBusy: false,
  dense: false,
  embedded: false,
  errorMessage: '',
  fullHeight: false,
  kicker: '',
  retryLabel: '',
  subtitle: '',
})

const emit = defineEmits<{
  retry: []
}>()

</script>

<template>
  <section
    :aria-busy="ariaBusy ? 'true' : undefined"
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

    <FeedbackAlert
      v-if="errorMessage"
      :message="errorMessage"
      :retry-label="retryLabel"
      @retry="emit('retry')"
    />

    <slot name="alerts" />

    <div class="workbench-page__body">
      <slot />
    </div>
  </section>
</template>
