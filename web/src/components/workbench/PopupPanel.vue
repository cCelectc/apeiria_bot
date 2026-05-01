<template>
  <v-dialog
    :max-width="maxWidth"
    :model-value="modelValue"
    scrollable
    @update:model-value="emit('update:modelValue', $event)"
  >
    <v-card class="workbench-popup-panel">
      <v-card-title class="workbench-popup-panel__title">
        <span>{{ title }}</span>

        <v-btn
          v-if="closable"
          :aria-label="closeLabel"
          icon="mdi-close"
          variant="text"
          @click="emit('update:modelValue', false)"
        />
      </v-card-title>

      <v-card-text class="workbench-popup-panel__body">
        <slot />
      </v-card-text>

      <v-card-actions v-if="$slots.actions" class="workbench-popup-panel__actions">
        <slot name="actions" />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    modelValue: boolean
    title: string
    maxWidth?: string | number
    closeLabel?: string
    closable?: boolean
  }>(), {
    closable: true,
    closeLabel: 'Close',
    maxWidth: 760,
  })

  const emit = defineEmits<{
    'update:modelValue': [value: boolean]
  }>()
</script>

<style scoped>
.workbench-popup-panel__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px 6px !important;
  font-weight: 720;
}

.workbench-popup-panel__body {
  min-width: 0;
  padding-top: 12px !important;
}

.workbench-popup-panel__actions {
  padding: 8px 18px 16px !important;
}
</style>
