<template>
  <div :class="cn('flex flex-col gap-4', $attrs.class as string)">
    <template v-for="field in visibleFields" :key="field.key">
      <div :class="{ 'ml-4 border-l-2 border-border pl-4': depth > 0 }">
        <SettingsFieldEditor
          :field="field"
          :model-value="getValue(field.key)"
          :depth="depth"
          :disabled="disabled || field.immutable"
          @update:model-value="onFieldChange(field.key, $event)"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { cn } from "@/lib/utils"
import type { SettingsFieldItem } from "@/types/settings"
import SettingsFieldEditor from "./SettingsFieldEditor.vue"

const props = withDefaults(defineProps<{
  fields: SettingsFieldItem[]
  modelValue: Record<string, unknown>
  disabled?: boolean
  depth?: number
  class?: string
}>(), {
  disabled: false,
  depth: 0,
})

const emit = defineEmits<{
  "update:modelValue": [value: Record<string, unknown>]
}>()

const visibleFields = computed(() => props.fields)

function getValue(key: string): unknown {
  return props.modelValue[key] ?? undefined
}

function onFieldChange(key: string, value: unknown) {
  const next = { ...props.modelValue }
  if (value === undefined || value === null) {
    delete next[key]
  } else {
    next[key] = value
  }
  emit("update:modelValue", next)
}
</script>
