<template>
  <section class="workbench-resource">
    <div v-if="$slots.metrics" class="workbench-resource__metrics">
      <slot name="metrics" />
    </div>

    <div v-if="title || $slots.actions" class="workbench-resource__toolbar">
      <div v-if="title" class="workbench-resource__heading">
        <div class="workbench-resource__title">
          <v-icon v-if="icon" :icon="icon" size="20" />
          <span>{{ title }}</span>

          <v-chip v-if="count !== undefined" size="small" variant="tonal">
            {{ count }}
          </v-chip>
        </div>

        <div v-if="subtitle" class="workbench-resource__subtitle">{{ subtitle }}</div>
      </div>

      <div v-if="$slots.actions" class="workbench-resource__actions">
        <slot name="actions" />
      </div>
    </div>

    <div v-if="$slots.filters" class="workbench-resource__filters">
      <slot name="filters" />
    </div>

    <div v-if="loading" class="workbench-resource__loading">
      <v-skeleton-loader
        v-for="index in skeletonCount"
        :key="index"
        class="workbench-resource__skeleton"
        type="article"
      />
    </div>

    <slot v-else-if="!empty" />

    <slot v-else name="empty">
      <EmptyState
        :icon="emptyIcon"
        :text="emptyText"
        :title="emptyTitle"
      />
    </slot>
  </section>
</template>

<script setup lang="ts">
  import EmptyState from './EmptyState.vue'

  withDefaults(defineProps<{
    title?: string
    subtitle?: string
    icon?: string
    count?: string | number
    loading?: boolean
    empty?: boolean
    emptyTitle: string
    emptyText?: string
    emptyIcon?: string
    skeletonCount?: number
  }>(), {
    count: undefined,
    empty: false,
    emptyIcon: 'mdi-database-search-outline',
    emptyText: '',
    icon: '',
    loading: false,
    skeletonCount: 6,
    subtitle: '',
    title: '',
  })
</script>

<style scoped>
.workbench-resource {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 14px;
}

.workbench-resource__metrics {
  min-width: 0;
}

.workbench-resource__toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  gap: 12px;
  align-items: end;
  padding: 14px;
  border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
  border-radius: var(--shape-large);
  background: rgba(var(--v-theme-surface-container-low), 0.92);
}

.workbench-resource__heading {
  min-width: 0;
}

.workbench-resource__title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: rgb(var(--v-theme-on-surface));
  font-weight: 720;
  line-height: 1.3;
}

.workbench-resource__subtitle {
  margin-top: 4px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.86rem;
  line-height: 1.45;
}

.workbench-resource__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.workbench-resource__filters {
  min-width: 0;
}

.workbench-resource__actions {
  justify-content: flex-end;
}

.workbench-resource__loading {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}

.workbench-resource__skeleton {
  border-radius: var(--shape-medium);
}

@media (max-width: 980px) {
  .workbench-resource__toolbar {
    grid-template-columns: minmax(0, 1fr);
  }

  .workbench-resource__actions {
    justify-content: flex-start;
  }
}
</style>
