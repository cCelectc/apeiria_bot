<template>
  <section class="workbench-dense-list">
    <header v-if="title || subtitle || $slots.actions" class="workbench-dense-list__header">
      <div>
        <div v-if="title" class="workbench-dense-list__title">{{ title }}</div>
        <div v-if="subtitle" class="workbench-dense-list__subtitle">{{ subtitle }}</div>
      </div>

      <div v-if="$slots.actions" class="workbench-dense-list__actions">
        <slot name="actions" />
      </div>
    </header>

    <div class="workbench-dense-list__body">
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
.workbench-dense-list {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
  border-radius: var(--shape-large);
  background: rgb(var(--v-theme-surface-container-low));
}

.workbench-dense-list__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(var(--v-theme-outline-variant), 0.22);
}

.workbench-dense-list__title {
  color: rgb(var(--v-theme-on-surface));
  font-weight: 720;
}

.workbench-dense-list__subtitle {
  margin-top: 3px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.84rem;
}

.workbench-dense-list__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.workbench-dense-list__body {
  min-width: 0;
}
</style>
