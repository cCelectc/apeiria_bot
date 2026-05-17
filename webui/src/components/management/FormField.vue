<script setup lang="ts">
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from '@/components/ui/field'

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
  <Field
    class="workbench-form-field"
    :data-invalid="error ? true : undefined"
  >
    <FieldLabel :for="forId || undefined" class="workbench-form-field__label">
      <span>{{ label }}</span>
      <span v-if="required" aria-hidden="true">*</span>
    </FieldLabel>
    <slot />
    <FieldError v-if="error" class="workbench-form-field__error">
      {{ error }}
    </FieldError>
    <FieldDescription v-else-if="helper" class="workbench-form-field__helper">
      {{ helper }}
    </FieldDescription>
  </Field>
</template>
