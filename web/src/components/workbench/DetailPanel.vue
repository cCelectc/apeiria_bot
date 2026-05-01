<template>
  <section class="workbench-detail-panel" :class="{ 'workbench-detail-panel--flat': flat }">
    <header v-if="title || subtitle || $slots.actions || $slots.meta" class="workbench-detail-panel__header">
      <div class="workbench-detail-panel__heading">
        <div v-if="title" class="workbench-detail-panel__title">{{ title }}</div>
        <div v-if="subtitle" class="workbench-detail-panel__subtitle">{{ subtitle }}</div>
        <slot name="meta" />
      </div>

      <div v-if="$slots.actions" class="workbench-detail-panel__actions">
        <slot name="actions" />
      </div>
    </header>

    <div class="workbench-detail-panel__body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    title?: string
    subtitle?: string
    flat?: boolean
  }>(), {
    flat: false,
    subtitle: '',
    title: '',
  })
</script>

<style scoped>
.workbench-detail-panel {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
  border-radius: var(--shape-large);
  background: rgb(var(--v-theme-surface-container-low));
}

.workbench-detail-panel--flat {
  background: transparent;
}

.workbench-detail-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.workbench-detail-panel__heading,
.workbench-detail-panel__body {
  min-width: 0;
}

.workbench-detail-panel__title {
  color: rgb(var(--v-theme-on-surface));
  font-size: 1.05rem;
  font-weight: 760;
  line-height: 1.3;
}

.workbench-detail-panel__subtitle {
  margin-top: 3px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  line-height: 1.45;
}

.workbench-detail-panel__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.workbench-detail-panel__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
