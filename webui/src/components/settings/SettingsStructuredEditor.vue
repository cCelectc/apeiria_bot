<script setup lang="ts">
import { Plus, Trash2 } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import {
  buildSchemaFieldDefaultValue,
  cloneSettingValue,
  displayChoiceTitle,
  displayFieldValue,
  type SettingSchema,
} from '@/utils/settingsEditor'

defineOptions({
  name: 'SettingsStructuredEditor',
})

const props = withDefaults(defineProps<{
  modelValue: unknown
  readonly?: boolean
  schema: SettingSchema
}>(), {
  readonly: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: unknown]
}>()

const { t } = useI18n()

const nullKey = '__settings:null'
const trueKey = '__settings:true'
const falseKey = '__settings:false'

const nullableBoolOptions = [
  { key: nullKey, title: 'null', value: null },
  { key: trueKey, title: 'true', value: true },
  { key: falseKey, title: 'false', value: false },
]

const choiceOptions = computed(() =>
  props.schema.choices.map((choice, index) => ({
    key: `choice:${index}`,
    title: displayChoiceTitle(choice),
    value: choice.value,
  })),
)

const selectedChoiceKey = computed(() => {
  const option = choiceOptions.value.find(item => isSameChoiceValue(item.value, props.modelValue))
  return option?.key
})

const selectedNullableBoolKey = computed(() => {
  if (props.modelValue === null) {
    return nullKey
  }
  return props.modelValue ? trueKey : falseKey
})

const objectValue = computed<Record<string, unknown>>(() =>
  isPlainObject(props.modelValue) ? props.modelValue : {},
)

const sequenceValue = computed<unknown[]>(() =>
  Array.isArray(props.modelValue) ? props.modelValue : [],
)

const mappingEntries = computed(() => {
  if (!isPlainObject(props.modelValue)) {
    return []
  }
  return Object.entries(props.modelValue).map(([key, value]) => ({ key, value }))
})

const itemSchema = computed(() => props.schema.item_schema)
const valueSchema = computed(() => props.schema.value_schema)

const isChoiceSchema = computed(() => props.schema.choices.length > 0)
const isNullableBool = computed(() =>
  props.schema.type === 'bool' && props.schema.allows_null,
)
const isScalarSchema = computed(() =>
  props.schema.type === 'str'
  || props.schema.type === 'int'
  || props.schema.type === 'float'
  || props.schema.type === 'Path'
  || props.schema.type === 'timedelta'
  || props.schema.type.startsWith('IPv')
  || props.schema.type.startsWith('Any'),
)
const isObjectSchema = computed(() =>
  props.schema.fields.length > 0
  && props.schema.type !== 'dict'
  && props.schema.type !== 'list'
  && props.schema.type !== 'set',
)
const isSequenceSchema = computed(() =>
  (props.schema.type === 'list' || props.schema.type === 'set') && Boolean(itemSchema.value),
)
const isMappingSchema = computed(() =>
  props.schema.type === 'dict' && Boolean(valueSchema.value),
)

function selectChoice(key: unknown) {
  const option = choiceOptions.value.find(item => item.key === String(key))
  if (option) {
    emit('update:modelValue', cloneSettingValue(option.value))
  }
}

function selectNullableBool(key: unknown) {
  const option = nullableBoolOptions.find(item => item.key === String(key))
  if (option) {
    emit('update:modelValue', option.value)
  }
}

function updateObjectField(key: string, value: unknown) {
  emit('update:modelValue', {
    ...clonePlainObject(objectValue.value),
    [key]: cloneSettingValue(value),
  })
}

function updateSequenceItem(index: number, value: unknown) {
  emit('update:modelValue', sequenceValue.value.map((item, currentIndex) =>
    currentIndex === index ? cloneSettingValue(value) : cloneSettingValue(item),
  ))
}

function appendSequenceItem() {
  if (!itemSchema.value) {
    return
  }
  emit('update:modelValue', [
    ...sequenceValue.value.map(item => cloneSettingValue(item)),
    buildSchemaFieldDefaultValue(itemSchema.value),
  ])
}

function removeSequenceItem(index: number) {
  emit('update:modelValue', sequenceValue.value
    .filter((_, currentIndex) => currentIndex !== index)
    .map(item => cloneSettingValue(item)))
}

function updateMappingKey(index: number, key: string | number) {
  const nextEntries = mappingEntries.value.map((entry, currentIndex) =>
    currentIndex === index
      ? { key: String(key), value: cloneSettingValue(entry.value) }
      : { key: entry.key, value: cloneSettingValue(entry.value) },
  )
  emit('update:modelValue', Object.fromEntries(nextEntries.map(entry => [entry.key, entry.value])))
}

function updateMappingValue(index: number, value: unknown) {
  const nextEntries = mappingEntries.value.map((entry, currentIndex) =>
    currentIndex === index
      ? { key: entry.key, value: cloneSettingValue(value) }
      : { key: entry.key, value: cloneSettingValue(entry.value) },
  )
  emit('update:modelValue', Object.fromEntries(nextEntries.map(entry => [entry.key, entry.value])))
}

function appendMappingEntry() {
  if (!valueSchema.value) {
    return
  }
  const nextKey = buildNextMappingKey(mappingEntries.value.map(entry => entry.key))
  emit('update:modelValue', {
    ...clonePlainObject(objectValue.value),
    [nextKey]: buildSchemaFieldDefaultValue(valueSchema.value),
  })
}

function removeMappingEntry(index: number) {
  const nextEntries = mappingEntries.value
    .filter((_, currentIndex) => currentIndex !== index)
    .map(entry => [entry.key, cloneSettingValue(entry.value)] as const)
  emit('update:modelValue', Object.fromEntries(nextEntries))
}

function buildNextMappingKey(existingKeys: string[]) {
  const usedKeys = new Set(existingKeys)
  let index = 1
  while (usedKeys.has(`key_${index}`)) {
    index += 1
  }
  return `key_${index}`
}

function inputMode(schema: SettingSchema) {
  if (schema.type === 'int') {
    return 'numeric'
  }
  if (schema.type === 'float') {
    return 'decimal'
  }
  return undefined
}

function isSameChoiceValue(left: unknown, right: unknown) {
  return JSON.stringify(left) === JSON.stringify(right)
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function clonePlainObject(value: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, cloneSettingValue(item)]),
  )
}
</script>

<template>
  <div class="settings-structured-editor">
    <Select
      v-if="isChoiceSchema"
      :model-value="selectedChoiceKey"
      :disabled="readonly"
      @update:model-value="selectChoice"
    >
      <SelectTrigger class="settings-field-editor__control">
        <SelectValue :placeholder="t('common.none')" />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectItem
            v-for="choice in choiceOptions"
            :key="choice.key"
            :value="choice.key"
          >
            {{ choice.title }}
          </SelectItem>
        </SelectGroup>
      </SelectContent>
    </Select>

    <Select
      v-else-if="isNullableBool"
      :model-value="selectedNullableBoolKey"
      :disabled="readonly"
      @update:model-value="selectNullableBool"
    >
      <SelectTrigger class="settings-field-editor__control">
        <SelectValue :placeholder="t('common.none')" />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectItem
            v-for="option in nullableBoolOptions"
            :key="option.key"
            :value="option.key"
          >
            {{ option.title }}
          </SelectItem>
        </SelectGroup>
      </SelectContent>
    </Select>

    <label v-else-if="schema.type === 'bool'" class="settings-field-editor__switch">
      <Switch
        :disabled="readonly"
        :model-value="Boolean(modelValue)"
        @update:model-value="value => emit('update:modelValue', Boolean(value))"
      />
      <span>{{ modelValue ? t('ai.enabled') : t('ai.disabled') }}</span>
    </label>

    <Input
      v-else-if="isScalarSchema"
      :model-value="modelValue == null ? '' : String(modelValue)"
      :disabled="readonly"
      type="text"
      :inputmode="inputMode(schema)"
      class="settings-field-editor__control"
      @update:model-value="value => emit('update:modelValue', value)"
    />

    <FieldSet v-else-if="isObjectSchema" class="settings-structured-editor__fieldset">
      <FieldGroup class="settings-structured-editor__group">
        <Field
          v-for="field in schema.fields"
          :key="field.key"
          class="settings-structured-editor__field"
        >
          <FieldLabel>{{ field.label || field.key }}</FieldLabel>
          <FieldDescription v-if="field.help">
            {{ field.help }}
          </FieldDescription>
          <SettingsStructuredEditor
            :model-value="objectValue[field.key]"
            :readonly="readonly"
            :schema="field.schema"
            @update:model-value="value => updateObjectField(field.key, value)"
          />
        </Field>
      </FieldGroup>
    </FieldSet>

    <FieldSet v-else-if="isSequenceSchema" class="settings-structured-editor__fieldset">
      <FieldGroup class="settings-structured-editor__group">
        <Field
          v-for="(item, index) in sequenceValue"
          :key="index"
          class="settings-structured-editor__collection-item"
        >
          <div class="settings-structured-editor__toolbar">
            <FieldLegend variant="label">#{{ index + 1 }}</FieldLegend>
            <Button
              v-if="!readonly"
              type="button"
              size="icon"
              variant="ghost"
              :aria-label="t('common.delete')"
              @click="removeSequenceItem(index)"
            >
              <Trash2 data-icon="inline-start" />
            </Button>
          </div>
          <SettingsStructuredEditor
            v-if="itemSchema"
            :model-value="item"
            :readonly="readonly"
            :schema="itemSchema.schema"
            @update:model-value="value => updateSequenceItem(index, value)"
          />
        </Field>
      </FieldGroup>
      <Button
        v-if="!readonly"
        type="button"
        variant="outline"
        size="sm"
        class="settings-structured-editor__add"
        @click="appendSequenceItem"
      >
        <Plus data-icon="inline-start" />
        {{ t('common.add') }}
      </Button>
    </FieldSet>

    <FieldSet v-else-if="isMappingSchema" class="settings-structured-editor__fieldset">
      <FieldGroup class="settings-structured-editor__group">
        <Field
          v-for="(entry, index) in mappingEntries"
          :key="`${entry.key}:${index}`"
          class="settings-structured-editor__mapping-item"
        >
          <Field class="settings-structured-editor__mapping-key">
            <FieldLabel>Key</FieldLabel>
            <Input
              :model-value="entry.key"
              :disabled="readonly"
              class="settings-field-editor__control"
              @update:model-value="value => updateMappingKey(index, value)"
            />
          </Field>
          <div class="settings-structured-editor__mapping-value">
            <SettingsStructuredEditor
              v-if="valueSchema"
              :model-value="entry.value"
              :readonly="readonly"
              :schema="valueSchema.schema"
              @update:model-value="value => updateMappingValue(index, value)"
            />
          </div>
          <Button
            v-if="!readonly"
            type="button"
            size="icon"
            variant="ghost"
            :aria-label="t('common.delete')"
            @click="removeMappingEntry(index)"
          >
            <Trash2 data-icon="inline-start" />
          </Button>
        </Field>
      </FieldGroup>
      <Button
        v-if="!readonly"
        type="button"
        variant="outline"
        size="sm"
        class="settings-structured-editor__add"
        @click="appendMappingEntry"
      >
        <Plus data-icon="inline-start" />
        {{ t('common.add') }}
      </Button>
    </FieldSet>

    <Textarea
      v-else
      :model-value="displayFieldValue(modelValue)"
      class="settings-field-editor__code"
      readonly
      :rows="3"
      spellcheck="false"
    />
  </div>
</template>
