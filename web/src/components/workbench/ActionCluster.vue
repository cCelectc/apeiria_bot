<template>
  <div class="workbench-action-cluster" :class="`workbench-action-cluster--${align}`">
    <slot />

    <v-menu v-if="$slots.overflow" location="bottom end" offset="8">
      <template #activator="{ props }">
        <v-btn
          v-bind="props"
          :aria-label="overflowLabel"
          class="workbench-action-cluster__overflow"
          density="comfortable"
          icon="mdi-dots-horizontal"
          variant="text"
        />
      </template>

      <v-list class="workbench-action-cluster__overflow-list" density="compact">
        <slot name="overflow" />
      </v-list>
    </v-menu>
  </div>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    align?: 'start' | 'end' | 'stretch'
    overflowLabel?: string
  }>(), {
    align: 'end',
    overflowLabel: 'More actions',
  })
</script>

<style scoped>
.workbench-action-cluster {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.workbench-action-cluster--start {
  justify-content: flex-start;
}

.workbench-action-cluster--end {
  justify-content: flex-end;
}

.workbench-action-cluster--stretch {
  align-items: stretch;
}

.workbench-action-cluster__overflow {
  flex: 0 0 auto;
}

.workbench-action-cluster__overflow-list {
  min-width: 180px;
}

@media (max-width: 640px) {
  .workbench-action-cluster {
    justify-content: flex-start;
  }
}
</style>
