<template>
  <v-card class="workbench-log-panel page-panel">
    <div class="workbench-log-panel__head">
      <div aria-hidden="true" class="workbench-log-panel__dots">
        <span />
        <span />
        <span />
      </div>

      <span class="workbench-log-panel__title">{{ title }}</span>

      <div v-if="$slots.actions" class="workbench-log-panel__actions">
        <slot name="actions" />
      </div>
    </div>

    <div v-if="!empty" class="workbench-log-panel__body">
      <slot />
    </div>

    <EmptyState
      v-else
      class="workbench-log-panel__empty"
      icon="mdi-text-box-search-outline"
      :text="emptyText"
      :title="loading ? loadingText : emptyTitle"
    />
  </v-card>
</template>

<script setup lang="ts">
  import EmptyState from './EmptyState.vue'

  withDefaults(defineProps<{
    title: string
    emptyTitle: string
    emptyText?: string
    loadingText: string
    loading?: boolean
    empty?: boolean
  }>(), {
    empty: false,
    emptyText: '',
    loading: false,
  })
</script>

<style scoped>
.workbench-log-panel {
  display: flex;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  overflow: hidden;
  border-color: rgba(var(--v-theme-outline-variant), var(--surface-border-opacity)) !important;
}

.workbench-log-panel__head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 46px;
  padding: 0 14px;
  border-bottom: 1px solid rgba(var(--v-theme-outline-variant), 0.22);
  background: rgba(var(--v-theme-surface-container), 0.72);
}

.workbench-log-panel__dots {
  display: inline-flex;
  gap: 5px;
}

.workbench-log-panel__dots span {
  width: 8px;
  height: 8px;
  border-radius: var(--shape-pill);
  background: rgba(var(--v-theme-on-surface), 0.28);
}

.workbench-log-panel__title {
  color: rgba(var(--v-theme-on-surface), 0.72);
  font-family: var(--font-family-mono);
  font-size: 0.84rem;
}

.workbench-log-panel__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.workbench-log-panel__body {
  min-height: 0;
  flex: 1 1 auto;
  background: rgb(var(--v-theme-surface));
}

.workbench-log-panel__empty {
  margin: 16px;
}
</style>
