<template>
  <v-card class="workbench-data-panel page-panel">
    <div v-if="title || $slots.actions" class="workbench-data-panel__header">
      <div>
        <div v-if="title" class="workbench-data-panel__title">{{ title }}</div>
        <div v-if="subtitle" class="workbench-data-panel__subtitle">{{ subtitle }}</div>
      </div>

      <div v-if="$slots.actions" class="workbench-data-panel__actions">
        <slot name="actions" />
      </div>
    </div>

    <slot />
  </v-card>
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
.workbench-data-panel {
  overflow: hidden;
  border-color: rgba(var(--v-theme-outline-variant), var(--surface-border-opacity)) !important;
}

.workbench-data-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px 0;
}

.workbench-data-panel__title {
  color: rgb(var(--v-theme-on-surface));
  font-weight: 720;
}

.workbench-data-panel__subtitle {
  margin-top: 4px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.86rem;
}

.workbench-data-panel__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}
</style>
