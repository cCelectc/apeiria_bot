<template>
  <section class="workbench-selectable-list">
    <header v-if="title || subtitle || $slots.actions" class="workbench-selectable-list__header">
      <div class="workbench-selectable-list__heading">
        <div v-if="title" class="workbench-selectable-list__title">{{ title }}</div>
        <div v-if="subtitle" class="workbench-selectable-list__subtitle">{{ subtitle }}</div>
      </div>

      <div v-if="$slots.actions" class="workbench-selectable-list__actions">
        <slot name="actions" />
      </div>
    </header>

    <div v-if="$slots.filters" class="workbench-selectable-list__filters">
      <slot name="filters" />
    </div>

    <div class="workbench-selectable-list__body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    title?: string
    subtitle?: string
  }>(), {
    subtitle: '',
    title: '',
  })
</script>

<style scoped>
.workbench-selectable-list {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
  border-radius: var(--shape-large);
  background: rgb(var(--v-theme-surface-container-low));
}

.workbench-selectable-list__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.workbench-selectable-list__heading,
.workbench-selectable-list__filters,
.workbench-selectable-list__body {
  min-width: 0;
}

.workbench-selectable-list__title {
  color: rgb(var(--v-theme-on-surface));
  font-weight: 720;
}

.workbench-selectable-list__subtitle {
  margin-top: 3px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.82rem;
}

.workbench-selectable-list__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.workbench-selectable-list__body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  overflow-x: hidden;
}
</style>
