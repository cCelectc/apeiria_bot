<script setup lang="ts">
import { Plus, X } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
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
  cloneSettingValue,
  displayChoiceTitle,
  displayFieldValue,
  isNestedEditorField,
  isNullableBoolField,
  isSequenceChipField,
  textInputType,
  type SettingField,
} from '@/utils/settingsEditor'
import SettingsStructuredEditor from './SettingsStructuredEditor.vue'

defineOptions({
  name: 'SettingsFieldEditor',
})

const props = withDefaults(defineProps<{
  arrayHint?: string
  editing: boolean
  field: SettingField
  jsonHint?: string
  modelValue: unknown
  readonlyRows?: number
  showReadonly?: boolean
}>(), {
  arrayHint: '',
  jsonHint: '',
  readonlyRows: 2,
  showReadonly: true,
})

const emit = defineEmits<{
  'update:modelValue': [value: unknown]
}>()

const { t } = useI18n()
const chipDraft = ref('')

const canEdit = computed(() => props.editing && props.field.editable)

const choiceOptions = computed(() => {
  if (props.field.choices.length > 0) {
    return props.field.choices.map((choice, index) => ({
      key: `${props.field.key}:choice:${index}`,
      title: displayChoiceTitle(choice),
      value: choice.value,
    }))
  }
  if (isNullableBoolField(props.field)) {
    return [
      { key: `${props.field.key}:nullable:null`, title: 'null', value: null },
      { key: `${props.field.key}:nullable:true`, title: 'true', value: true },
      { key: `${props.field.key}:nullable:false`, title: 'false', value: false },
    ]
  }
  return []
})

const selectedChoiceKey = computed(() => {
  const option = choiceOptions.value.find(item =>
    JSON.stringify(item.value) === JSON.stringify(props.modelValue),
  )
  return option?.key
})

const chips = computed(() =>
  Array.isArray(props.modelValue)
    ? props.modelValue.map(item => displayFieldValue(item))
    : [],
)

const textareaValue = computed(() => {
  const value = canEdit.value ? props.modelValue : props.field.current_value
  return typeof value === 'string' || typeof value === 'number'
    ? value
    : displayFieldValue(value)
})

const readonlyValue = computed(() =>
  displayFieldValue(props.field.current_value),
)

function updateChoice(key: unknown) {
  const option = choiceOptions.value.find(item => item.key === String(key))
  if (option) {
    emit('update:modelValue', cloneSettingValue(option.value))
  }
}

function updateText(value: string | number) {
  emit('update:modelValue', value)
}

function addChip() {
  const value = chipDraft.value.trim()
  if (!value) {
    return
  }
  emit('update:modelValue', [...chips.value, value])
  chipDraft.value = ''
}

function removeChip(index: number) {
  emit('update:modelValue', chips.value.filter((_, currentIndex) => currentIndex !== index))
}

function useReadonlyTextarea(field: SettingField) {
  return isNestedEditorField(field)
    || field.type_category === 'mapping'
    || field.type_category === 'sequence'
}
</script>

<template>
  <div class="settings-field-editor">
    <Select
      v-if="canEdit && choiceOptions.length > 0"
      :model-value="selectedChoiceKey"
      :disabled="!canEdit"
      @update:model-value="updateChoice"
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

    <label
      v-else-if="canEdit && field.type === 'bool' && !isNullableBoolField(field)"
      class="settings-field-editor__switch"
    >
      <Switch
        :disabled="!canEdit"
        :model-value="Boolean(modelValue)"
        @update:model-value="value => emit('update:modelValue', Boolean(value))"
      />
      <span>{{ modelValue ? t('ai.enabled') : t('ai.disabled') }}</span>
    </label>

    <FieldGroup v-else-if="canEdit && isSequenceChipField(field)" class="settings-field-editor__chips">
      <Field class="settings-field-editor__chip-list">
        <span
          v-for="(chip, index) in chips"
          :key="`${chip}:${index}`"
          class="settings-field-editor__chip"
        >
          <span>{{ chip }}</span>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            :aria-label="t('common.delete')"
            @click="removeChip(index)"
          >
            <X data-icon="inline-start" />
          </Button>
        </span>
      </Field>
      <Field class="settings-field-editor__chip-input" orientation="responsive">
        <FieldLabel class="sr-only">{{ field.label || field.key }}</FieldLabel>
        <Input
          v-model="chipDraft"
          class="settings-field-editor__control"
          @keydown.enter.prevent="addChip"
        />
        <Button type="button" size="sm" variant="outline" @click="addChip">
          <Plus data-icon="inline-start" />
          {{ t('common.add') }}
        </Button>
      </Field>
    </FieldGroup>

    <SettingsStructuredEditor
      v-else-if="isNestedEditorField(field) && field.schema"
      :model-value="canEdit ? modelValue : field.current_value"
      :readonly="!canEdit"
      :schema="field.schema"
      @update:model-value="value => emit('update:modelValue', value)"
    />

    <Field v-else-if="canEdit && field.editor === 'json_array'">
      <Textarea
        :model-value="textareaValue"
        class="settings-field-editor__code"
        spellcheck="false"
        @update:model-value="updateText"
      />
      <FieldDescription v-if="arrayHint">{{ arrayHint }}</FieldDescription>
    </Field>

    <Field v-else-if="canEdit && field.editor === 'json_object'">
      <Textarea
        :model-value="textareaValue"
        class="settings-field-editor__code"
        spellcheck="false"
        @update:model-value="updateText"
      />
      <FieldDescription v-if="jsonHint">{{ jsonHint }}</FieldDescription>
    </Field>

    <Input
      v-else-if="canEdit"
      :model-value="modelValue == null ? '' : String(modelValue)"
      class="settings-field-editor__control"
      :type="textInputType(field)"
      @update:model-value="updateText"
    />

    <Textarea
      v-else-if="showReadonly && useReadonlyTextarea(field)"
      :model-value="readonlyValue"
      class="settings-field-editor__code"
      readonly
      :rows="readonlyRows"
      spellcheck="false"
    />

    <Input
      v-else-if="showReadonly"
      :model-value="readonlyValue"
      class="settings-field-editor__control"
      readonly
    />
  </div>
</template>
