<script setup lang="ts">
import type {
  AIRuntimeSettingFieldItem,
  AIRuntimeSettingValue,
  AIRuntimeSettingsResponse,
} from '@/api/ai'
import type { Component } from 'vue'
import {
  AlertCircle,
  Clock3,
  Gauge,
  RotateCcw,
  Save,
  Settings2,
  SlidersHorizontal,
  Volume2,
} from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import { getAIRuntimeSettings, updateAIRuntimeSettings } from '@/api/ai'
import {
  EmptyState,
  LoadingSkeleton,
  PageScaffold,
  Panel,
  StatusBadge,
} from '@/components/management'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { useNoticeStore } from '@/stores/notice'

type AIRuntimeSettingGroupKey =
  | 'reply_policy'
  | 'ingress_media'
  | 'runtime_limits'
  | 'retention'

type AIRuntimeSettingGroupMeta = {
  descriptionKey: string
  icon: Component
  key: AIRuntimeSettingGroupKey
  labelKey: string
}

type AIRuntimeSettingGroupView = AIRuntimeSettingGroupMeta & {
  advancedFields: AIRuntimeSettingFieldItem[]
  defaultFields: AIRuntimeSettingFieldItem[]
}

const props = withDefaults(defineProps<{
  embedded?: boolean
}>(), {
  embedded: false,
})

const { t, te } = useI18n()
const noticeStore = useNoticeStore()
const settings = ref<AIRuntimeSettingsResponse | null>(null)
const form = reactive<Record<string, AIRuntimeSettingValue>>({})
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const validationMessage = ref('')
const dirtyKeys = ref<Set<string>>(new Set())

const groupMeta: AIRuntimeSettingGroupMeta[] = [
  {
    descriptionKey: 'ai.runtimeSettingsGroup.replyPolicyDescription',
    icon: SlidersHorizontal,
    key: 'reply_policy',
    labelKey: 'ai.runtimeSettingsGroup.replyPolicy',
  },
  {
    descriptionKey: 'ai.runtimeSettingsGroup.ingressMediaDescription',
    icon: Volume2,
    key: 'ingress_media',
    labelKey: 'ai.runtimeSettingsGroup.ingressMedia',
  },
  {
    descriptionKey: 'ai.runtimeSettingsGroup.runtimeLimitsDescription',
    icon: Gauge,
    key: 'runtime_limits',
    labelKey: 'ai.runtimeSettingsGroup.runtimeLimits',
  },
  {
    descriptionKey: 'ai.runtimeSettingsGroup.retentionDescription',
    icon: Clock3,
    key: 'retention',
    labelKey: 'ai.runtimeSettingsGroup.retention',
  },
]

const groupedFields = computed<AIRuntimeSettingGroupView[]>(() =>
  groupMeta.map(group => {
    const fields = (settings.value?.fields || [])
      .filter(field => field.group === group.key && field.visibility !== 'hidden')
      .sort(compareSettingFields)
    return {
      ...group,
      advancedFields: fields.filter(field => field.visibility === 'advanced'),
      defaultFields: fields.filter(field => field.visibility !== 'advanced'),
    }
  }).filter(group => (
    group.defaultFields.length > 0 || group.advancedFields.length > 0
  )),
)

const hasSettings = computed(() => Boolean(settings.value))
const hasPendingChanges = computed(() => dirtyKeys.value.size > 0)
const overrideCount = computed(() => Object.keys(settings.value?.overrides || {}).length)
const updatedAtLabel = computed(() => (
  settings.value?.updated_at
    ? new Date(settings.value.updated_at).toLocaleString()
    : t('ai.runtimeSettingsNeverSaved')
))

function isBooleanField(field: AIRuntimeSettingFieldItem) {
  return field.value_type === 'boolean'
}

function isNumericField(field: AIRuntimeSettingFieldItem) {
  return field.value_type === 'integer' || field.value_type === 'float'
}

function compareSettingFields(
  left: AIRuntimeSettingFieldItem,
  right: AIRuntimeSettingFieldItem,
) {
  return left.order - right.order || left.key.localeCompare(right.key)
}

function cloneFieldValue(value: AIRuntimeSettingValue): AIRuntimeSettingValue {
  return value
}

function applyResponse(response: AIRuntimeSettingsResponse) {
  settings.value = response
  for (const field of response.fields) {
    form[field.key] = cloneFieldValue(field.current_value)
  }
  dirtyKeys.value = new Set()
  validationMessage.value = ''
}

async function loadSettings() {
  loading.value = true
  errorMessage.value = ''
  try {
    applyResponse((await getAIRuntimeSettings()).data)
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.runtimeSettingsLoadFailed'))
  } finally {
    loading.value = false
  }
}

function updateDirtyState(field: AIRuntimeSettingFieldItem) {
  const next = new Set(dirtyKeys.value)
  if (valuesEqual(form[field.key], field.current_value)) {
    next.delete(field.key)
  } else {
    next.add(field.key)
  }
  dirtyKeys.value = next
}

function updateBooleanField(field: AIRuntimeSettingFieldItem, value: boolean) {
  form[field.key] = value
  updateDirtyState(field)
}

function updateNumericField(field: AIRuntimeSettingFieldItem, value: string | number) {
  form[field.key] = value === '' ? null : Number(value)
  updateDirtyState(field)
}

function cancelField(field: AIRuntimeSettingFieldItem) {
  form[field.key] = cloneFieldValue(field.current_value)
  updateDirtyState(field)
}

async function clearField(field: AIRuntimeSettingFieldItem) {
  saving.value = true
  validationMessage.value = ''
  try {
    applyResponse((await updateAIRuntimeSettings({ clear: [field.key] })).data)
    noticeStore.show(t('ai.runtimeSettingsResetSaved'), 'success')
  } catch (error) {
    validationMessage.value = getErrorMessage(error, t('ai.runtimeSettingsSaveFailed'))
  } finally {
    saving.value = false
  }
}

async function saveSettings() {
  if (!settings.value || dirtyKeys.value.size === 0) {
    return
  }
  const invalid = findInvalidField()
  if (invalid) {
    validationMessage.value = t('ai.runtimeSettingsInvalidField', {
      field: fieldLabel(invalid),
    })
    return
  }
  saving.value = true
  validationMessage.value = ''
  const values: Record<string, AIRuntimeSettingValue> = {}
  for (const key of dirtyKeys.value) {
    values[key] = form[key]
  }
  try {
    applyResponse((await updateAIRuntimeSettings({ values })).data)
    noticeStore.show(t('ai.runtimeSettingsSaved'), 'success')
  } catch (error) {
    validationMessage.value = getErrorMessage(error, t('ai.runtimeSettingsSaveFailed'))
  } finally {
    saving.value = false
  }
}

function findInvalidField() {
  const fields = settings.value?.fields || []
  return fields.find(field => {
    if (!dirtyKeys.value.has(field.key) || !isNumericField(field)) {
      return false
    }
    const value = form[field.key]
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return true
    }
    return field.minimum !== null && value < field.minimum
  })
}

function valuesEqual(left: AIRuntimeSettingValue, right: AIRuntimeSettingValue) {
  return left === right
}

function displayValue(value: AIRuntimeSettingValue) {
  if (typeof value === 'boolean') {
    return value ? t('plugins.settingsYes') : t('plugins.settingsNo')
  }
  if (value === null || value === undefined) {
    return t('common.none')
  }
  return String(value)
}

function inputValue(field: AIRuntimeSettingFieldItem): string | number {
  const value = form[field.key]
  return typeof value === 'number' || typeof value === 'string' ? value : ''
}

function localizedText(key: string, fallback: string) {
  return te(key) ? t(key) : fallback
}

function fieldLabel(field: AIRuntimeSettingFieldItem) {
  return localizedText(field.label_key, field.label || field.key)
}

function fieldHelp(field: AIRuntimeSettingFieldItem) {
  return localizedText(field.help_key, field.help || '')
}

onMounted(() => {
  void loadSettings()
})
</script>

<template>
  <PageScaffold
    dense
    :embedded="props.embedded"
    :error-message="errorMessage"
    :subtitle="props.embedded ? '' : t('ai.pageSubtitle.runtimeSettings')"
    :title="t('ai.runtimeSettingsTitle')"
  >
    <template #meta>
      <Badge variant="secondary">
        {{ t('ai.runtimeSettingsOverrides', { count: overrideCount }) }}
      </Badge>
      <Badge variant="outline">
        {{ t('ai.runtimeSettingsUpdatedAt', { value: updatedAtLabel }) }}
      </Badge>
    </template>

    <template #actions>
      <Button
        :disabled="loading || saving"
        size="sm"
        variant="outline"
        @click="loadSettings"
      >
        <RotateCcw data-icon="inline-start" />
        {{ t('common.refresh') }}
      </Button>
      <Button
        :disabled="!hasPendingChanges || loading || saving"
        size="sm"
        @click="saveSettings"
      >
        <Save data-icon="inline-start" />
        {{ t('common.save') }}
      </Button>
    </template>

    <template #alerts>
      <Alert v-if="validationMessage" variant="destructive">
        <AlertCircle data-icon="inline-start" />
        <AlertTitle>{{ t('ai.runtimeSettingsValidationTitle') }}</AlertTitle>
        <AlertDescription>{{ validationMessage }}</AlertDescription>
      </Alert>
    </template>

    <LoadingSkeleton v-if="loading && !hasSettings" rows="8" />

    <EmptyState
      v-else-if="!hasSettings"
      :icon="Settings2"
      :text="t('ai.runtimeSettingsEmptyDescription')"
      :title="t('ai.runtimeSettingsEmptyTitle')"
    />

    <div v-else class="ai-runtime-settings-grid">
      <Panel
        v-for="group in groupedFields"
        :key="group.key"
        :subtitle="t(group.descriptionKey)"
        :title="t(group.labelKey)"
      >
        <template #actions>
          <component :is="group.icon" class="ai-runtime-settings-group-icon" />
        </template>

        <FieldGroup class="ai-runtime-settings-list">
          <Field
            v-for="field in group.defaultFields"
            :key="field.key"
            class="ai-runtime-settings-field"
          >
            <div class="ai-runtime-settings-field__main">
              <div class="ai-runtime-settings-field__copy">
                <div class="ai-runtime-settings-field__title-row">
                  <FieldLabel>{{ fieldLabel(field) }}</FieldLabel>
                  <StatusBadge
                    v-if="field.has_local_override"
                    :label="t('plugins.settingsLocalShort')"
                    tone="info"
                  />
                </div>
                <FieldDescription>{{ fieldHelp(field) }}</FieldDescription>
              </div>

              <div class="ai-runtime-settings-field__control">
                <label
                  v-if="isBooleanField(field)"
                  class="ai-runtime-settings-switch"
                >
                  <Switch
                    :disabled="saving"
                    :model-value="Boolean(form[field.key])"
                    @update:model-value="value => updateBooleanField(field, Boolean(value))"
                  />
                  <span>
                    {{ form[field.key] ? t('ai.enabled') : t('ai.disabled') }}
                  </span>
                </label>

                <Input
                  v-else
                  :aria-invalid="field === findInvalidField()"
                  :disabled="saving"
                  :min="field.minimum ?? undefined"
                  :model-value="inputValue(field)"
                  :step="field.value_type === 'float' ? '0.1' : '1'"
                  class="ai-runtime-settings-input"
                  type="number"
                  @update:model-value="value => updateNumericField(field, value)"
                />
              </div>
            </div>

            <div class="ai-runtime-settings-field__meta">
              <Badge variant="outline">
                {{ t('plugins.settingsCurrent') }}:
                {{ displayValue(form[field.key]) }}
              </Badge>
              <Badge variant="outline">
                {{ t('plugins.settingsDefault') }}:
                {{ displayValue(field.default_value) }}
              </Badge>
              <Badge v-if="field.minimum !== null" variant="outline">
                {{ t('ai.runtimeSettingsMinimum', { value: field.minimum }) }}
              </Badge>
            </div>

            <div
              v-if="dirtyKeys.has(field.key) || field.has_local_override"
              class="ai-runtime-settings-field__actions"
            >
              <Button
                v-if="dirtyKeys.has(field.key)"
                :disabled="saving"
                size="sm"
                variant="ghost"
                @click="cancelField(field)"
              >
                {{ t('common.cancel') }}
              </Button>
              <Button
                v-if="field.has_local_override"
                :disabled="saving"
                size="sm"
                variant="ghost"
                @click="clearField(field)"
              >
                {{ t('plugins.settingsClear') }}
              </Button>
            </div>
            <Separator />
          </Field>

          <details
            v-if="group.advancedFields.length > 0"
            class="ai-runtime-settings-advanced"
          >
            <summary class="ai-runtime-settings-advanced__summary">
              <span>{{ t('ai.runtimeSettingsAdvanced') }}</span>
              <Badge variant="outline">
                {{ t('ai.runtimeSettingsAdvancedCount', { count: group.advancedFields.length }) }}
              </Badge>
            </summary>

            <Field
              v-for="field in group.advancedFields"
              :key="field.key"
              class="ai-runtime-settings-field"
            >
              <div class="ai-runtime-settings-field__main">
                <div class="ai-runtime-settings-field__copy">
                  <div class="ai-runtime-settings-field__title-row">
                    <FieldLabel>{{ fieldLabel(field) }}</FieldLabel>
                    <StatusBadge
                      v-if="field.has_local_override"
                      :label="t('plugins.settingsLocalShort')"
                      tone="info"
                    />
                  </div>
                  <FieldDescription>{{ fieldHelp(field) }}</FieldDescription>
                </div>

                <div class="ai-runtime-settings-field__control">
                  <label
                    v-if="isBooleanField(field)"
                    class="ai-runtime-settings-switch"
                  >
                    <Switch
                      :disabled="saving"
                      :model-value="Boolean(form[field.key])"
                      @update:model-value="value => updateBooleanField(field, Boolean(value))"
                    />
                    <span>
                      {{ form[field.key] ? t('ai.enabled') : t('ai.disabled') }}
                    </span>
                  </label>

                  <Input
                    v-else
                    :aria-invalid="field === findInvalidField()"
                    :disabled="saving"
                    :min="field.minimum ?? undefined"
                    :model-value="inputValue(field)"
                    :step="field.value_type === 'float' ? '0.1' : '1'"
                    class="ai-runtime-settings-input"
                    type="number"
                    @update:model-value="value => updateNumericField(field, value)"
                  />
                </div>
              </div>

              <div class="ai-runtime-settings-field__meta">
                <Badge variant="outline">
                  {{ t('plugins.settingsCurrent') }}:
                  {{ displayValue(form[field.key]) }}
                </Badge>
                <Badge variant="outline">
                  {{ t('plugins.settingsDefault') }}:
                  {{ displayValue(field.default_value) }}
                </Badge>
                <Badge v-if="field.minimum !== null" variant="outline">
                  {{ t('ai.runtimeSettingsMinimum', { value: field.minimum }) }}
                </Badge>
              </div>

              <div
                v-if="dirtyKeys.has(field.key) || field.has_local_override"
                class="ai-runtime-settings-field__actions"
              >
                <Button
                  v-if="dirtyKeys.has(field.key)"
                  :disabled="saving"
                  size="sm"
                  variant="ghost"
                  @click="cancelField(field)"
                >
                  {{ t('common.cancel') }}
                </Button>
                <Button
                  v-if="field.has_local_override"
                  :disabled="saving"
                  size="sm"
                  variant="ghost"
                  @click="clearField(field)"
                >
                  {{ t('plugins.settingsClear') }}
                </Button>
              </div>
              <Separator />
            </Field>
          </details>
        </FieldGroup>
      </Panel>
    </div>
  </PageScaffold>
</template>
