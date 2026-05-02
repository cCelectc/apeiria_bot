<template>
  <div class="settings-field-editor">
    <v-switch
      v-if="editing && field.editable && field.editor === 'switch' && !isNullableBoolField(field)"
      color="primary"
      hide-details
      inset
      :model-value="modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <v-select
      v-else-if="editing && field.editable && isNullableBoolField(field)"
      :density="density"
      hide-details
      item-title="title"
      item-value="value"
      :items="nullableBoolItems"
      :model-value="modelValue"
      variant="outlined"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <v-select
      v-else-if="editing && field.editable && field.editor === 'select'"
      :density="density"
      hide-details
      item-title="title"
      item-value="value"
      :items="field.choices"
      :model-value="modelValue"
      variant="outlined"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <v-text-field
      v-else-if="editing && field.editable && isTextInputField(field)"
      :density="density"
      hide-details
      :model-value="modelValue"
      :placeholder="field.secret ? '' : displayFieldValue(field.current_value)"
      :type="textInputType(field)"
      variant="outlined"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <v-combobox
      v-else-if="editing && field.editable && isSequenceChipField(field)"
      chips
      closable-chips
      :density="density"
      hide-details
      :model-value="modelValue"
      multiple
      variant="outlined"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <SettingsStructuredEditor
      v-else-if="isNestedEditorField(field) && field.schema"
      :model-value="editing && field.editable ? modelValue : field.current_value"
      :readonly="!editing || !field.editable"
      :schema="field.schema"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <v-textarea
      v-else-if="editing && field.editable && field.editor === 'json_array'"
      auto-grow
      :density="density"
      :hint="arrayHint"
      :model-value="modelValue"
      persistent-hint
      rows="4"
      variant="outlined"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <v-textarea
      v-else-if="editing && field.editable && field.editor === 'json_object'"
      auto-grow
      :density="density"
      :hint="jsonHint"
      :model-value="modelValue"
      persistent-hint
      rows="4"
      variant="outlined"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <v-textarea
      v-else-if="showReadonly && useReadonlyTextarea(field)"
      auto-grow
      :density="density"
      hide-details
      :model-value="displayFieldValue(field.current_value)"
      readonly
      :rows="readonlyRows"
      variant="outlined"
    />

    <v-text-field
      v-else-if="showReadonly"
      :density="density"
      hide-details
      :model-value="displayFieldValue(field.current_value)"
      readonly
      variant="outlined"
    />
  </div>
</template>

<script setup lang="ts">
  import {
    displayFieldValue,
    isNestedEditorField,
    isNullableBoolField,
    isSequenceChipField,
    isTextInputField,
    type PluginSettingField,
    textInputType,
  } from './settingsEditor'
  import SettingsStructuredEditor from './SettingsStructuredEditor.vue'

  withDefaults(defineProps<{
    arrayHint: string
    density?: 'default' | 'comfortable' | 'compact'
    editing: boolean
    field: PluginSettingField
    jsonHint: string
    modelValue: unknown
    readonlyRows?: number
    showReadonly?: boolean
  }>(), {
    density: 'comfortable',
    readonlyRows: 2,
    showReadonly: true,
  })

  const emit = defineEmits<{
    'update:modelValue': [value: unknown]
  }>()

  const nullableBoolItems = [
    { title: 'null', value: null },
    { title: 'true', value: true },
    { title: 'false', value: false },
  ]

  function useReadonlyTextarea (field: PluginSettingField) {
    return field.type_category === 'mapping' || field.type_category === 'sequence'
  }
</script>

<style scoped>
.settings-field-editor {
  width: 100%;
}

.settings-field-editor :deep(.v-selection-control) {
  margin-inline: 0;
}
</style>
