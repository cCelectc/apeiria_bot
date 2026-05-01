<template>
  <button
    :aria-pressed="active"
    class="workbench-selectable-list-item"
    :class="{
      'workbench-selectable-list-item--active': active,
      'workbench-selectable-list-item--disabled': disabled,
      'workbench-selectable-list-item--warning': warning,
    }"
    :disabled="disabled"
    type="button"
  >
    <div class="workbench-selectable-list-item__main">
      <span class="workbench-selectable-list-item__title">{{ title }}</span>
      <span v-if="subtitle" class="workbench-selectable-list-item__subtitle">{{ subtitle }}</span>
    </div>

    <div v-if="$slots.meta || meta || count !== undefined" class="workbench-selectable-list-item__meta">
      <slot name="meta">
        <span v-if="meta">{{ meta }}</span>
        <span v-if="count !== undefined" class="workbench-selectable-list-item__count">{{ count }}</span>
      </slot>
    </div>
  </button>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    title: string
    subtitle?: string
    meta?: string
    count?: number | string
    active?: boolean
    disabled?: boolean
    warning?: boolean
  }>(), {
    active: false,
    count: undefined,
    disabled: false,
    meta: '',
    subtitle: '',
    warning: false,
  })
</script>

<style scoped>
.workbench-selectable-list-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid rgba(var(--v-theme-outline-variant), 0.2);
  border-radius: var(--shape-medium);
  background: rgb(var(--v-theme-surface));
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition:
    border-color var(--motion-fast) var(--motion-ease),
    background-color var(--motion-fast) var(--motion-ease),
    transform var(--motion-fast) var(--motion-ease);
}

.workbench-selectable-list-item:hover {
  border-color: rgba(var(--v-theme-primary), 0.32);
  background: rgba(var(--v-theme-primary), 0.04);
}

.workbench-selectable-list-item:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.workbench-selectable-list-item:active {
  transform: translateY(1px);
}

.workbench-selectable-list-item--active {
  border-color: rgba(var(--v-theme-primary), 0.46);
  background: rgba(var(--v-theme-primary), 0.1);
}

.workbench-selectable-list-item--warning {
  border-color: rgba(var(--v-theme-warning), 0.38);
}

.workbench-selectable-list-item--disabled {
  cursor: default;
  opacity: 0.58;
}

.workbench-selectable-list-item__main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.workbench-selectable-list-item__title {
  overflow: hidden;
  color: rgb(var(--v-theme-on-surface));
  font-weight: 700;
  line-height: 1.35;
  text-overflow: ellipsis;
}

.workbench-selectable-list-item__subtitle {
  overflow: hidden;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.82rem;
  line-height: 1.35;
  text-overflow: ellipsis;
}

.workbench-selectable-list-item__meta {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 5px;
}

.workbench-selectable-list-item__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 7px;
  border-radius: var(--shape-small);
  background: rgba(var(--v-theme-primary), 0.1);
  color: rgb(var(--v-theme-primary));
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  line-height: 1;
}
</style>
