<template>
  <div class="workbench-empty-state">
    <div v-if="icon" class="workbench-empty-state__icon">
      <v-icon :icon="icon" size="30" />
    </div>

    <div class="workbench-empty-state__content">
      <div class="workbench-empty-state__title">{{ title }}</div>
      <div v-if="text" class="workbench-empty-state__text">{{ text }}</div>
    </div>

    <div v-if="$slots.actions || actionLabel" class="workbench-empty-state__actions">
      <slot name="actions">
        <v-btn
          v-if="actionLabel"
          :prepend-icon="actionIcon"
          variant="tonal"
          @click="$emit('action')"
        >
          {{ actionLabel }}
        </v-btn>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
  defineEmits<{
    action: []
  }>()

  withDefaults(defineProps<{
    title: string
    text?: string
    icon?: string
    actionLabel?: string
    actionIcon?: string
  }>(), {
    actionIcon: '',
    actionLabel: '',
    icon: 'mdi-information-outline',
    text: '',
  })
</script>

<style scoped>
.workbench-empty-state {
  display: flex;
  min-height: 148px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 28px;
  border: 1px dashed rgba(var(--v-theme-outline), 0.24);
  border-radius: var(--shape-large);
  background: rgba(var(--v-theme-surface-container), 0.48);
  text-align: center;
}

.workbench-empty-state__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}

.workbench-empty-state__title {
  color: rgb(var(--v-theme-on-surface));
  font-weight: 700;
  line-height: 1.35;
}

.workbench-empty-state__text {
  max-width: 58ch;
  margin-top: 4px;
  color: rgba(var(--v-theme-on-surface), 0.66);
  font-size: 0.92rem;
  line-height: 1.55;
}

.workbench-empty-state__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}
</style>
