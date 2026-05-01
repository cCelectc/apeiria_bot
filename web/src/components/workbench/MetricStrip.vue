<template>
  <div class="workbench-metric-strip" :class="{ 'workbench-metric-strip--compact': compact }">
    <v-sheet
      v-for="item in items"
      :key="item.key"
      class="workbench-metric-strip__item"
    >
      <div class="workbench-metric-strip__label">{{ item.label }}</div>

      <div class="workbench-metric-strip__value-row">
        <div class="workbench-metric-strip__value">{{ item.value }}</div>

        <div
          v-if="item.icon"
          class="workbench-metric-strip__icon"
          :class="item.color ? `workbench-metric-strip__icon--${item.color}` : undefined"
        >
          <v-icon :icon="item.icon" size="22" />
        </div>
      </div>

      <div v-if="item.hint" class="workbench-metric-strip__hint">{{ item.hint }}</div>
    </v-sheet>
  </div>
</template>

<script setup lang="ts">
  interface WorkbenchMetricItem {
    key: string
    label: string
    value: string | number
    hint?: string
    icon?: string
    color?: string
  }

  withDefaults(defineProps<{
    items: WorkbenchMetricItem[]
    compact?: boolean
  }>(), {
    compact: false,
  })
</script>

<style scoped>
.workbench-metric-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}

.workbench-metric-strip--compact {
  grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
}

.workbench-metric-strip__item {
  min-width: 0;
  padding: 14px;
  border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
  background: rgba(var(--v-theme-surface-container), 0.9) !important;
  box-shadow: none;
}

.workbench-metric-strip__label {
  color: rgba(var(--v-theme-on-surface), 0.66);
  font-size: 0.82rem;
  font-weight: 650;
  line-height: 1.3;
}

.workbench-metric-strip__value-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
}

.workbench-metric-strip__value {
  min-width: 0;
  color: rgb(var(--v-theme-on-surface));
  font-size: 1.55rem;
  font-variant-numeric: tabular-nums;
  font-weight: 760;
  line-height: 1.1;
}

.workbench-metric-strip--compact .workbench-metric-strip__value {
  font-size: 1.25rem;
}

.workbench-metric-strip__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  border-radius: var(--shape-small);
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}

.workbench-metric-strip__icon--success {
  background: rgba(var(--v-theme-success), 0.14);
  color: rgb(var(--v-theme-success));
}

.workbench-metric-strip__icon--warning {
  background: rgba(var(--v-theme-warning), 0.14);
  color: rgb(var(--v-theme-warning));
}

.workbench-metric-strip__icon--info {
  background: rgba(var(--v-theme-info), 0.14);
  color: rgb(var(--v-theme-info));
}

.workbench-metric-strip__hint {
  margin-top: 6px;
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 0.78rem;
  line-height: 1.35;
}
</style>
