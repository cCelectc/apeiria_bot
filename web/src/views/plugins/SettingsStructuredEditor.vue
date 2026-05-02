<template>
  <div class="settings-structured-editor">
    <v-select
      v-if="schema.choices.length > 0"
      density="comfortable"
      :disabled="readonly"
      hide-details
      item-title="title"
      item-value="value"
      :items="choiceItems"
      :model-value="modelValue"
      variant="outlined"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <v-select
      v-else-if="isNullableBoolSchema(schema)"
      density="comfortable"
      :disabled="readonly"
      hide-details
      item-title="title"
      item-value="value"
      :items="nullableBoolItems"
      :model-value="modelValue"
      variant="outlined"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <v-switch
      v-else-if="schema.type === 'bool'"
      color="primary"
      :disabled="readonly"
      hide-details
      inset
      :model-value="Boolean(modelValue)"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <v-text-field
      v-else-if="isScalarSchema(schema)"
      density="comfortable"
      hide-details
      :model-value="modelValue"
      :readonly="readonly"
      :type="schema.type === 'int' || schema.type === 'float' ? 'number' : 'text'"
      variant="outlined"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <div v-else-if="isObjectSchema(schema)" class="structured-object">
      <div
        v-for="field in schema.fields"
        :key="field.key"
        class="structured-object__row workbench-field-row"
      >
        <div class="structured-object__meta workbench-field-row__meta">
          <div class="workbench-field__title">{{ field.label || field.key }}</div>
          <div v-if="field.help" class="workbench-field__helper">
            {{ field.help }}
          </div>
        </div>
        <SettingsStructuredEditor
          class="workbench-field-row__control"
          :model-value="objectValue[field.key]"
          :readonly="readonly"
          :schema="field.schema"
          @update:model-value="updateObjectField(field.key, $event)"
        />
      </div>
    </div>

    <div v-else-if="isSequenceSchema(schema)" class="structured-list">
      <div
        v-for="(item, index) in sequenceValue"
        :key="index"
        class="structured-list__item"
      >
        <div class="structured-list__item-toolbar">
          <span class="workbench-field__title">#{{ index + 1 }}</span>
          <v-btn
            v-if="!readonly"
            color="warning"
            icon="mdi-delete-outline"
            size="x-small"
            variant="text"
            @click="removeSequenceItem(index)"
          />
        </div>
        <SettingsStructuredEditor
          v-if="itemSchema"
          :model-value="item"
          :readonly="readonly"
          :schema="itemSchema.schema"
          @update:model-value="updateSequenceItem(index, $event)"
        />
      </div>
      <v-btn
        v-if="!readonly"
        block
        color="primary"
        prepend-icon="mdi-plus"
        variant="tonal"
        @click="appendSequenceItem"
      >
        {{ t('common.add') }}
      </v-btn>
    </div>

    <div v-else-if="isMappingSchema(schema)" class="structured-map">
      <div
        v-for="(entry, index) in mappingEntries"
        :key="`${entry.key}:${index}`"
        class="structured-map__row"
      >
        <label class="workbench-field structured-map__key">
          <span class="workbench-field__title">Key</span>
          <v-text-field
            :aria-label="`Key ${index + 1}`"
            class="workbench-field__control"
            density="comfortable"
            hide-details
            :model-value="entry.key"
            :readonly="readonly"
            variant="outlined"
            @update:model-value="updateMappingKey(index, String($event ?? ''))"
          />
        </label>
        <SettingsStructuredEditor
          v-if="valueSchema"
          class="structured-map__value"
          :model-value="entry.value"
          :readonly="readonly"
          :schema="valueSchema.schema"
          @update:model-value="updateMappingValue(index, $event)"
        />
        <v-btn
          v-if="!readonly"
          color="warning"
          icon="mdi-delete-outline"
          size="small"
          variant="text"
          @click="removeMappingEntry(index)"
        />
      </div>
      <v-btn
        v-if="!readonly"
        block
        color="primary"
        prepend-icon="mdi-plus"
        variant="tonal"
        @click="appendMappingEntry"
      >
        {{ t('common.add') }}
      </v-btn>
    </div>

    <v-textarea
      v-else
      auto-grow
      density="comfortable"
      hide-details
      :model-value="displayFieldValue(modelValue)"
      readonly
      rows="3"
      variant="outlined"
    />
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'

  import {
    buildSchemaFieldDefaultValue,
    cloneSettingValue,
    displayChoiceTitle,
    displayFieldValue,
    type PluginSettingSchema,
  } from './settingsEditor'

  defineOptions({
    name: 'SettingsStructuredEditor',
  })

  const props = withDefaults(defineProps<{
    modelValue: unknown
    readonly?: boolean
    schema: PluginSettingSchema
  }>(), {
    readonly: false,
  })
  const { t } = useI18n()

  const emit = defineEmits<{
    'update:modelValue': [value: unknown]
  }>()

  const nullableBoolItems = [
    { title: 'null', value: null },
    { title: 'true', value: true },
    { title: 'false', value: false },
  ]

  const choiceItems = computed(() =>
    props.schema.choices.map(choice => ({
      title: displayChoiceTitle(choice),
      value: choice.value,
    })),
  )

  const objectValue = computed<Record<string, unknown>>(() => {
    if (props.modelValue && typeof props.modelValue === 'object' && !Array.isArray(props.modelValue)) {
      return props.modelValue as Record<string, unknown>
    }
    return {}
  })

  const sequenceValue = computed<unknown[]>(() =>
    Array.isArray(props.modelValue) ? props.modelValue : [],
  )

  const itemSchema = computed(() => props.schema.item_schema)
  const valueSchema = computed(() => props.schema.value_schema)

  const mappingEntries = computed(() => {
    if (!props.modelValue || typeof props.modelValue !== 'object' || Array.isArray(props.modelValue)) {
      return []
    }
    return Object.entries(props.modelValue as Record<string, unknown>).map(([key, value]) => ({
      key,
      value,
    }))
  })

  function isNullableBoolSchema (schema: PluginSettingSchema) {
    return schema.type === 'bool' && schema.allows_null
  }

  function isScalarSchema (schema: PluginSettingSchema) {
    return schema.type === 'str'
      || schema.type === 'int'
      || schema.type === 'float'
      || schema.type === 'Path'
      || schema.type === 'timedelta'
      || schema.type.startsWith('IPv')
      || schema.type.startsWith('Any')
  }

  function isObjectSchema (schema: PluginSettingSchema) {
    return schema.fields.length > 0 && schema.type !== 'dict' && schema.type !== 'list' && schema.type !== 'set'
  }

  function isSequenceSchema (schema: PluginSettingSchema) {
    return (schema.type === 'list' || schema.type === 'set') && Boolean(schema.item_schema)
  }

  function isMappingSchema (schema: PluginSettingSchema) {
    return schema.type === 'dict' && Boolean(schema.value_schema)
  }

  function updateObjectField (key: string, value: unknown) {
    emit('update:modelValue', {
      ...objectValue.value,
      [key]: value,
    })
  }

  function updateSequenceItem (index: number, value: unknown) {
    const nextValue = sequenceValue.value.map((item, currentIndex) =>
      currentIndex === index ? value : cloneSettingValue(item),
    )
    emit('update:modelValue', nextValue)
  }

  function appendSequenceItem () {
    if (!itemSchema.value) return
    emit('update:modelValue', [
      ...sequenceValue.value.map(item => cloneSettingValue(item)),
      buildSchemaFieldDefaultValue(itemSchema.value),
    ])
  }

  function removeSequenceItem (index: number) {
    emit('update:modelValue', sequenceValue.value.filter((_, currentIndex) => currentIndex !== index))
  }

  function appendMappingEntry () {
    if (!valueSchema.value) return
    const nextEntries = [...mappingEntries.value]
    const nextKey = buildNextMappingKey(nextEntries.map(entry => entry.key))
    nextEntries.push({
      key: nextKey,
      value: buildSchemaFieldDefaultValue(valueSchema.value),
    })
    emit('update:modelValue', Object.fromEntries(nextEntries.map(entry => [entry.key, entry.value])))
  }

  function updateMappingKey (index: number, value: string) {
    const nextEntries = mappingEntries.value.map((entry, currentIndex) =>
      currentIndex === index ? { ...entry, key: value } : { ...entry, value: cloneSettingValue(entry.value) },
    )
    emit('update:modelValue', Object.fromEntries(nextEntries.map(entry => [entry.key, entry.value])))
  }

  function updateMappingValue (index: number, value: unknown) {
    const nextEntries = mappingEntries.value.map((entry, currentIndex) =>
      currentIndex === index ? { ...entry, value } : { ...entry, value: cloneSettingValue(entry.value) },
    )
    emit('update:modelValue', Object.fromEntries(nextEntries.map(entry => [entry.key, entry.value])))
  }

  function removeMappingEntry (index: number) {
    const nextEntries = mappingEntries.value.filter((_, currentIndex) => currentIndex !== index)
    emit('update:modelValue', Object.fromEntries(nextEntries.map(entry => [entry.key, entry.value])))
  }

  function buildNextMappingKey (existingKeys: string[]) {
    const usedKeys = new Set(existingKeys)
    if (!usedKeys.has('key_1')) return 'key_1'
    let index = 2
    while (usedKeys.has(`key_${index}`)) {
      index += 1
    }
    return `key_${index}`
  }
</script>

<style scoped>
.settings-structured-editor {
  width: 100%;
}

.structured-object,
.structured-list,
.structured-map {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.structured-object__row,
.structured-list__item,
.structured-map__row {
  padding: 10px;
  border-radius: var(--shape-small);
  border: 1px solid rgba(var(--v-theme-outline), 0.18);
  background: rgba(var(--v-theme-surface), 0.82);
  transition:
    border-color var(--motion-fast) var(--motion-ease),
    box-shadow var(--motion-fast) var(--motion-ease);
}

.structured-list__item,
.structured-map__row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.structured-object__row:focus-within,
.structured-list__item:focus-within,
.structured-map__row:focus-within {
  border-color: rgba(var(--v-theme-primary), 0.3);
  box-shadow: var(--focus-ring);
}

.structured-object__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.structured-list__item-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.structured-map__key {
  flex: 0 0 auto;
}

.structured-map__value {
  flex: 1 1 auto;
}

@media (min-width: 720px) {
  .structured-map__row {
    display: grid;
    grid-template-columns: minmax(160px, 220px) minmax(0, 1fr) auto;
    align-items: start;
  }
}
</style>
