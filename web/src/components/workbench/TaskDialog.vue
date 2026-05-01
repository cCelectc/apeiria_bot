<template>
  <v-dialog v-model="visible" :max-width="maxWidth">
    <v-card class="workbench-task-dialog">
      <v-card-title class="workbench-task-dialog__title">
        <span>{{ title }}</span>

        <v-chip
          v-if="status"
          :color="loading ? color : statusColor"
          size="small"
          variant="tonal"
        >
          {{ status }}
        </v-chip>
      </v-card-title>

      <v-card-text class="workbench-task-dialog__body">
        <slot name="details" />
        <v-progress-linear v-if="loading" :color="color" indeterminate />

        <div class="workbench-task-dialog__log">
          <pre>{{ logs || waitingText }}</pre>
        </div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />

        <v-btn :disabled="closeDisabled" variant="text" @click="visible = false">
          {{ closeLabel }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
  import { computed } from 'vue'

  const props = withDefaults(defineProps<{
    modelValue: boolean
    title: string
    status?: string
    logs?: string
    waitingText: string
    closeLabel: string
    color?: string
    maxWidth?: string | number
    loading?: boolean
    closeDisabled?: boolean
    statusColor?: string
  }>(), {
    closeDisabled: false,
    color: 'primary',
    loading: false,
    logs: '',
    maxWidth: 840,
    status: '',
    statusColor: 'default',
  })

  const emit = defineEmits<{
    'update:modelValue': [value: boolean]
  }>()

  const visible = computed({
    get: () => props.modelValue,
    set: value => emit('update:modelValue', value),
  })
</script>

<style scoped>
.workbench-task-dialog {
  overflow: hidden;
}

.workbench-task-dialog__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.workbench-task-dialog__body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.workbench-task-dialog__log {
  max-height: 48vh;
  overflow: auto;
  padding: 14px 16px;
  border-radius: var(--shape-small);
  background: rgb(var(--v-theme-surface-container-low));
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-outline-variant), 0.28);
}

.workbench-task-dialog__log pre {
  margin: 0;
  font-family: var(--font-family-mono);
  font-size: 0.84rem;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
