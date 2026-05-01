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
        <div v-if="kicker" class="workbench-page__kicker">{{ kicker }}</div>
        <h1 class="workbench-page__title">{{ title }}</h1>
        <p v-if="subtitle" class="workbench-page__subtitle">{{ subtitle }}</p>
        <slot name="meta" />
      </div>

      <div v-if="$slots.actions" class="workbench-page__actions">
        <slot name="actions" />
      </div>
    </header>

    <slot name="before" />

    <v-alert
      v-if="errorMessage"
      density="comfortable"
      type="error"
      variant="tonal"
    >
      {{ errorMessage }}
    </v-alert>

    <slot name="alerts" />

    <main class="workbench-page__body">
      <slot />
    </main>
  </section>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    title: string
    subtitle?: string
    kicker?: string
    errorMessage?: string
    dense?: boolean
    fullHeight?: boolean
  }>(), {
    dense: false,
    errorMessage: '',
    fullHeight: false,
    kicker: '',
    subtitle: '',
  })
</script>

<style scoped>
.workbench-page {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--workbench-stack-gap, 18px);
}

.workbench-page--full-height {
  height: calc(100dvh - var(--workbench-frame-offset, 40px));
  min-height: 0;
  max-height: calc(100dvh - var(--workbench-frame-offset, 40px));
  overflow: hidden;
}

.workbench-page--dense {
  --workbench-stack-gap: 14px;
}

.workbench-page__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: start;
  padding: var(--workbench-header-padding-y, 18px) var(--workbench-header-padding-x, 18px);
  border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
  border-radius: var(--shape-large);
  background:
    linear-gradient(180deg, rgba(var(--v-theme-surface-container), 0.9), rgba(var(--v-theme-surface-container-low), 0.98)),
    linear-gradient(135deg, rgba(var(--v-theme-primary), 0.025), transparent 56%);
  box-shadow: none;
}

.workbench-page__heading {
  min-width: 0;
}

.workbench-page__kicker {
  margin-bottom: 4px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.72rem;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.workbench-page__title {
  margin: 0;
  color: rgb(var(--v-theme-on-surface));
  font-size: clamp(1.55rem, 2.8vw, 2.05rem);
  font-weight: 760;
  line-height: 1.12;
  letter-spacing: 0;
  text-wrap: balance;
}

.workbench-page__subtitle {
  max-width: 72ch;
  margin: 8px 0 0;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 0.94rem;
  line-height: 1.55;
  text-wrap: pretty;
}

.workbench-page__actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.workbench-page__body {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  gap: var(--workbench-stack-gap, 18px);
}

.workbench-page--full-height .workbench-page__body {
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 760px) {
  .workbench-page--full-height {
    height: auto;
    max-height: none;
    overflow: visible;
  }

  .workbench-page--full-height .workbench-page__body {
    overflow: visible;
  }

  .workbench-page__header {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px;
  }

  .workbench-page__actions {
    justify-content: flex-start;
  }
}
</style>
