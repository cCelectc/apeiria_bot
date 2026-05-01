<template>
  <section
    class="workbench-filter-bar"
    :class="{
      'workbench-filter-bar--compact': compact,
      'workbench-filter-bar--inline': inline,
      'workbench-filter-bar--no-heading': !title && !subtitle && !$slots.heading,
    }"
  >
    <div v-if="title || subtitle || $slots.heading" class="workbench-filter-bar__heading">
      <slot name="heading">
        <div v-if="title" class="workbench-filter-bar__title">{{ title }}</div>
        <div v-if="subtitle" class="workbench-filter-bar__subtitle">{{ subtitle }}</div>
      </slot>
    </div>

    <div v-if="$slots.filters" class="workbench-filter-bar__filters">
      <slot name="filters" />
    </div>

    <div v-if="$slots.presets" class="workbench-filter-bar__presets">
      <slot name="presets" />
    </div>

    <div v-if="$slots.summary" class="workbench-filter-bar__summary">
      <slot name="summary" />
    </div>

    <div v-if="$slots.actions" class="workbench-filter-bar__actions">
      <slot name="actions" />

      <v-btn
        v-if="$slots.overflow"
        class="workbench-filter-bar__overflow-trigger"
        prepend-icon="mdi-filter-variant"
        variant="tonal"
        @click="overflowOpen = true"
      >
        {{ overflowLabel }}
      </v-btn>
    </div>

    <div v-else-if="$slots.overflow" class="workbench-filter-bar__actions">
      <v-btn
        class="workbench-filter-bar__overflow-trigger"
        prepend-icon="mdi-filter-variant"
        variant="tonal"
        @click="overflowOpen = true"
      >
        {{ overflowLabel }}
      </v-btn>
    </div>

    <div v-if="$slots.default" class="workbench-filter-bar__body">
      <slot />
    </div>
  </section>

  <v-dialog v-model="overflowOpen" max-width="760" scrollable>
    <v-card class="workbench-filter-bar__overflow-dialog">
      <v-card-title class="workbench-filter-bar__overflow-title">
        {{ overflowTitle || overflowLabel }}
      </v-card-title>

      <v-card-text class="workbench-filter-bar__overflow-body">
        <slot name="overflow" />
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="overflowOpen = false">
          {{ closeLabel }}
        </v-btn>
        <v-btn color="primary" variant="flat" @click="overflowOpen = false">
          {{ applyLabel }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
  import { ref } from 'vue'

  withDefaults(defineProps<{
    title?: string
    subtitle?: string
    compact?: boolean
    overflowLabel?: string
    overflowTitle?: string
    applyLabel?: string
    closeLabel?: string
    inline?: boolean
  }>(), {
    applyLabel: 'Apply',
    closeLabel: 'Close',
    compact: false,
    inline: false,
    overflowLabel: 'Filters',
    overflowTitle: '',
    subtitle: '',
    title: '',
  })

  const overflowOpen = ref(false)
</script>

<style scoped>
.workbench-filter-bar {
  display: grid;
  grid-template-columns: minmax(160px, 0.8fr) minmax(280px, 2fr) auto;
  gap: 12px;
  align-items: end;
  padding: 12px;
  border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
  border-radius: var(--shape-panel);
  background: rgba(var(--v-theme-surface-container-low), 0.92);
}

.workbench-filter-bar--compact {
  padding: 10px;
}

.workbench-filter-bar--inline {
  grid-template-columns: max-content minmax(260px, 1fr) max-content max-content;
  align-items: center;
}

.workbench-filter-bar--compact.workbench-filter-bar--no-heading {
  grid-template-columns: minmax(260px, 1fr) auto auto;
  align-items: center;
}

.workbench-filter-bar__heading,
.workbench-filter-bar__filters,
.workbench-filter-bar__presets,
.workbench-filter-bar__summary,
.workbench-filter-bar__actions,
.workbench-filter-bar__body {
  min-width: 0;
}

.workbench-filter-bar--no-heading .workbench-filter-bar__filters {
  grid-column: 1 / 3;
}

.workbench-filter-bar--compact.workbench-filter-bar--no-heading .workbench-filter-bar__filters,
.workbench-filter-bar--compact.workbench-filter-bar--no-heading .workbench-filter-bar__summary {
  grid-column: auto;
}

.workbench-filter-bar--compact.workbench-filter-bar--no-heading .workbench-filter-bar__actions {
  grid-column: -2 / -1;
}

.workbench-filter-bar--inline .workbench-filter-bar__heading,
.workbench-filter-bar--inline .workbench-filter-bar__filters,
.workbench-filter-bar--inline .workbench-filter-bar__presets,
.workbench-filter-bar--inline .workbench-filter-bar__actions {
  grid-column: auto;
}

.workbench-filter-bar--inline .workbench-filter-bar__title {
  white-space: nowrap;
}

.workbench-filter-bar--inline .workbench-filter-bar__filters,
.workbench-filter-bar--inline .workbench-filter-bar__presets,
.workbench-filter-bar--inline .workbench-filter-bar__actions {
  flex-wrap: nowrap;
}

.workbench-filter-bar__title {
  color: rgb(var(--v-theme-on-surface));
  font-weight: 720;
  line-height: 1.35;
}

.workbench-filter-bar__subtitle {
  margin-top: 3px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.84rem;
  line-height: 1.45;
}

.workbench-filter-bar__filters,
.workbench-filter-bar__presets,
.workbench-filter-bar__summary,
.workbench-filter-bar__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.workbench-filter-bar__filters > :deep(*) {
  flex: 1 1 min(var(--workbench-filter-min), 100%);
  min-width: min(var(--workbench-filter-min), 100%);
}

.workbench-filter-bar__actions {
  justify-content: flex-end;
}

.workbench-filter-bar__summary {
  grid-column: 1 / -1;
  gap: 6px;
}

.workbench-filter-bar__overflow-trigger {
  flex: 0 0 auto;
}

.workbench-filter-bar__body {
  grid-column: 1 / -1;
}

.workbench-filter-bar__overflow-title {
  padding: 16px 18px 6px !important;
  font-weight: 720;
}

.workbench-filter-bar__overflow-body {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  padding-top: 12px !important;
}

.workbench-filter-bar__overflow-body :deep(.v-switch) {
  align-self: center;
}

@media (max-width: 980px) {
  .workbench-filter-bar {
    grid-template-columns: minmax(0, 1fr);
  }

  .workbench-filter-bar--inline {
    grid-template-columns: minmax(0, 1fr);
  }

  .workbench-filter-bar--compact.workbench-filter-bar--no-heading {
    grid-template-columns: minmax(0, 1fr);
  }

  .workbench-filter-bar--no-heading .workbench-filter-bar__filters,
  .workbench-filter-bar--inline .workbench-filter-bar__heading,
  .workbench-filter-bar--inline .workbench-filter-bar__filters,
  .workbench-filter-bar--inline .workbench-filter-bar__presets,
  .workbench-filter-bar--inline .workbench-filter-bar__actions,
  .workbench-filter-bar--compact.workbench-filter-bar--no-heading .workbench-filter-bar__filters,
  .workbench-filter-bar--compact.workbench-filter-bar--no-heading .workbench-filter-bar__summary,
  .workbench-filter-bar--compact.workbench-filter-bar--no-heading .workbench-filter-bar__actions {
    grid-column: auto;
  }

  .workbench-filter-bar__actions {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .workbench-filter-bar__filters,
  .workbench-filter-bar__presets,
  .workbench-filter-bar__summary,
  .workbench-filter-bar__actions {
    align-items: stretch;
  }

  .workbench-filter-bar__filters > :deep(*),
  .workbench-filter-bar__actions > :deep(*) {
    flex-basis: 100%;
  }
}
</style>
