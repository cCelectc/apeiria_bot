<script setup lang="ts">
import { computed } from 'vue'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { StatusBadge } from '.'

const props = withDefaults(defineProps<{
  closeDisabled?: boolean
  closeLabel: string
  loading?: boolean
  logs?: string
  modelValue: boolean
  status?: string
  statusTone?: 'default' | 'success' | 'warning' | 'error' | 'info'
  title: string
  waitingText: string
}>(), {
  closeDisabled: false,
  loading: false,
  logs: '',
  status: '',
  statusTone: 'default',
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})
</script>

<template>
  <Dialog v-model:open="visible">
    <DialogContent class="workbench-task-dialog">
      <DialogHeader>
        <div class="workbench-task-dialog__title-row">
          <DialogTitle>{{ title }}</DialogTitle>
          <StatusBadge v-if="status" :label="status" :tone="loading ? 'info' : statusTone" />
        </div>
        <DialogDescription v-if="$slots.details">
          <slot name="details" />
        </DialogDescription>
      </DialogHeader>

      <div v-if="loading" class="workbench-progress" />

      <div class="workbench-task-dialog__log">
        <pre>{{ logs || waitingText }}</pre>
      </div>

      <DialogFooter>
        <Button :disabled="closeDisabled" variant="secondary" @click="visible = false">
          {{ closeLabel }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
