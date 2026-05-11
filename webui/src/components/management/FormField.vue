<script setup lang="ts">
import { Label } from '@/components/ui/label'

withDefaults(defineProps<{
  error?: string
  forId?: string
  helper?: string
  label: string
  required?: boolean
}>(), {
  error: '',
  forId: '',
  helper: '',
  required: false,
})
</script>

<template>
  <div class="workbench-form-field">
    <Label :for="forId || undefined" class="workbench-form-field__label">
      <span>{{ label }}</span>
      <span v-if="required" aria-hidden="true">*</span>
    </Label>
    <slot />
    <p v-if="error" class="workbench-form-field__error">
      {{ error }}
    </p>
    <p v-else-if="helper" class="workbench-form-field__helper">
      {{ helper }}
    </p>
  </div>
</template>
