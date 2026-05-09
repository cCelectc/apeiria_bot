<template>
  <v-sheet
    class="mb-4 source-workspace"
    :class="{ 'source-workspace--focused': focused }"
  >
    <header class="source-workspace__header">
      <div class="source-workspace__heading">
        <div class="source-workflow-step">
          <v-chip color="primary" size="small" variant="tonal">
            {{ t(focused ? 'ai.setupStep.connection' : 'ai.setupStep.provider') }}
          </v-chip>
          <div class="source-workflow-step__text">
            {{ t(focused ? 'ai.modelFlowStepHint.connection' : 'ai.providerWorkflowHint') }}
          </div>
        </div>
        <div v-if="sourceForm.preset_type" class="source-summary-line mt-2">
          <span>{{ t('ai.sourcePreset') }}：</span>
          <strong>{{ sourcePresetLabel(sourceForm.preset_type) }}</strong>
        </div>
      </div>
    </header>

    <div
      v-if="isCreatingSource"
      class="source-protocol-step"
      :class="{ 'source-protocol-step--focused': !sourceForm.preset_type }"
    >
      <div class="source-protocol-step__header">
        <div>
          <div class="source-protocol-step__title">
            {{ t('ai.sourceProtocolStepTitle') }}
          </div>
          <div class="source-protocol-step__hint">
            {{ t('ai.sourceProtocolStepHint') }}
          </div>
        </div>
      </div>
      <div v-if="sourcePresets.length > 0" class="source-protocol-grid">
        <button
          v-for="preset in sourcePresets"
          :key="preset.preset_type"
          :aria-pressed="sourceForm.preset_type === preset.preset_type"
          class="source-protocol-option"
          :class="{ 'source-protocol-option--active': sourceForm.preset_type === preset.preset_type }"
          type="button"
          @click="selectProtocol(preset.preset_type)"
        >
          <v-avatar class="source-protocol-option__avatar" color="primary" size="28" variant="tonal">
            {{ sourcePresetInitial(preset.preset_type) }}
          </v-avatar>
          <span class="source-protocol-option__body">
            <span class="source-protocol-option__title">
              {{ preset.display_name }}
            </span>
            <span class="source-protocol-option__text">
              {{ preset.description || t('ai.sourceProtocolDefaultHint') }}
            </span>
          </span>
        </button>
      </div>
      <div v-else class="empty-state-hint">
        {{ t('ai.sourceProtocolEmpty') }}
      </div>
    </div>

    <div v-if="workflow.connectionIssues.length > 0" class="source-issue-list">
      <v-chip
        v-for="issue in workflow.connectionIssues"
        :key="issue"
        color="warning"
        size="small"
        variant="tonal"
      >
        {{ connectionIssueLabel(issue) }}
      </v-chip>
    </div>

    <div class="source-config-list">
      <label class="source-config-field workbench-field">
        <span class="workbench-field__title">{{ t('ai.sourceName') }}</span>
        <span class="workbench-field__helper">{{ t('ai.sourceConfigNameHint') }}</span>
        <v-text-field
          v-model.trim="sourceForm.name"
          :aria-label="t('ai.sourceName')"
          class="workbench-field__control"
          density="comfortable"
          :disabled="savingSource"
          :error-messages="displayedSourceErrors.name ? [displayedSourceErrors.name] : []"
          hide-details="auto"
          @blur="touchSourceField('name')"
        />
      </label>

      <div class="source-config-field workbench-field">
        <div class="workbench-field__title">{{ t('ai.sourcePreset') }}</div>
        <div class="workbench-field__helper">{{ t('ai.sourceConfigPresetHint') }}</div>
        <div class="source-protocol-field">
          <v-select
            v-if="!isCreatingSource"
            v-model="sourceForm.preset_type"
            :aria-label="t('ai.sourcePreset')"
            density="comfortable"
            :disabled="savingSource"
            :error-messages="displayedSourceErrors.preset_type ? [displayedSourceErrors.preset_type] : []"
            hide-details="auto"
            :items="sourcePresetOptions"
            @blur="touchSourceField('preset_type')"
          />
          <div v-else class="source-protocol-field__value">
            {{ sourceForm.preset_type ? sourcePresetLabel(sourceForm.preset_type) : t('ai.sourceProtocolNotSelected') }}
          </div>
          <div v-if="displayedSourceErrors.preset_type" class="disabled-reason mt-1">
            {{ displayedSourceErrors.preset_type }}
          </div>
        </div>
      </div>

      <div class="source-config-field source-config-field--wide workbench-field">
        <div class="workbench-field__title">{{ t('ai.sourceApiKey') }}</div>
        <div class="workbench-field__helper">{{ t('ai.sourceConfigApiKeyHint') }}</div>
        <div class="source-api-key-field workbench-field-action-row">
          <v-text-field
            v-model.trim="sourcePrimaryApiKey"
            :aria-label="t('ai.sourceApiKey')"
            density="comfortable"
            hide-details
          />
          <v-btn
            class="source-api-key-field__action"
            :class="{ 'source-api-key-field__action--highlighted': highlight === 'connection' }"
            color="primary"
            variant="tonal"
            @click="openSourceApiKeysEditor"
          >
            {{ t('ai.sourceApiKeyManage') }}
          </v-btn>
        </div>
        <div v-if="extraSourceApiKeys.length > 0" class="source-api-key-inline-list">
          <div
            v-for="(item, index) in extraSourceApiKeys"
            :key="`${index}-${item}`"
            class="source-api-key-inline-item"
          >
            <span class="source-api-key-inline-item__value">{{ item }}</span>
            <v-btn
              :aria-label="t('common.delete')"
              density="comfortable"
              icon="mdi-close"
              size="x-small"
              variant="text"
              @click="removeExtraSourceApiKey(index)"
            />
          </div>
        </div>
      </div>

      <label class="source-config-field source-config-field--wide workbench-field">
        <span class="workbench-field__title">{{ t('ai.sourceApiBase') }}</span>
        <span class="workbench-field__helper">{{ t('ai.sourceConfigApiBaseHint') }}</span>
        <v-text-field
          v-model.trim="sourceForm.api_base"
          :aria-label="t('ai.sourceApiBase')"
          class="workbench-field__control"
          density="comfortable"
          :disabled="savingSource"
          hide-details
        />
      </label>
    </div>

    <div v-if="providerSaveDisabledReason" class="disabled-reason mt-3">
      {{ providerSaveDisabledReason }}
    </div>
    <AIWorkflowResultAlert :result="workflowResult" />

    <div class="source-form-actions">
      <v-btn prepend-icon="mdi-tune-variant" variant="tonal" @click="sourceAdvancedDialog = true">
        {{ t('ai.sourceAdvancedConfigAction') }}
      </v-btn>
      <div class="source-form-actions__primary">
        <v-btn
          v-if="sourceForm.source_id"
          color="error"
          :loading="deletingSource"
          variant="tonal"
          @click="removeSource"
        >
          {{ t('common.delete') }}
        </v-btn>
        <v-btn color="primary" :disabled="!canSaveSource" :loading="savingSource" @click="saveSource">
          {{ t('ai.saveSourceConfig') }}
        </v-btn>
      </div>
    </div>

    <v-dialog v-model="sourceApiKeysDialog" max-width="760">
      <v-card>
        <v-card-title class="text-h5 pt-6 px-6">
          {{ t('ai.sourceApiKeyManageTitle') }}
        </v-card-title>
        <v-card-text class="px-6">
          <div class="source-api-key-editor">
            <div class="source-api-key-editor__composer workbench-field-action-row">
              <label class="workbench-field">
                <span class="workbench-field__title">{{ t('ai.sourceApiKeyNew') }}</span>
                <v-text-field
                  v-model.trim="sourceApiKeyDraftInput"
                  :aria-label="t('ai.sourceApiKeyNew')"
                  class="workbench-field__control"
                  density="comfortable"
                  hide-details
                  @keydown.enter.prevent="appendSourceApiKeyDraft"
                />
              </label>
              <v-btn
                color="primary"
                variant="tonal"
                @click="appendSourceApiKeyDraft"
              >
                {{ t('ai.sourceApiKeyAdd') }}
              </v-btn>
            </div>
            <div class="source-api-key-editor__list">
              <div
                v-for="(item, index) in sourceApiKeyDraft"
                :key="`${index}-${item}`"
                class="source-api-key-editor__item"
              >
                <div class="source-api-key-editor__value">
                  {{ item }}
                </div>
                <v-btn
                  color="error"
                  icon="mdi-close"
                  size="small"
                  variant="text"
                  @click="removeSourceApiKeyDraft(index)"
                />
              </div>
            </div>
          </div>
        </v-card-text>
        <v-card-actions class="px-6 pb-6">
          <v-spacer />
          <v-btn variant="text" @click="sourceApiKeysDialog = false">
            {{ t('common.cancel') }}
          </v-btn>
          <v-btn color="primary" variant="text" @click="applySourceApiKeyDraft">
            {{ t('common.confirm') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <PopupPanel
      v-model="sourceAdvancedDialog"
      :close-label="t('common.close')"
      max-width="900"
      :title="t('ai.sourceAdvancedConfig')"
    >
      <div class="source-advanced-form workbench-form-grid pt-2">
        <label class="workbench-field">
          <span class="workbench-field__title">{{ t('ai.sourceAdapterKind') }}</span>
          <v-text-field
            v-model.trim="sourceForm.adapter_kind"
            :aria-label="t('ai.sourceAdapterKind')"
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
          />
        </label>
        <label class="workbench-field workbench-field--wide">
          <span class="workbench-field__title">{{ t('ai.capabilityMetadata') }}</span>
          <v-textarea
            v-model="sourceForm.capability_metadata_json"
            :aria-label="t('ai.capabilityMetadata')"
            auto-grow
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
            rows="2"
          />
        </label>
        <label class="workbench-field workbench-field--wide">
          <span class="workbench-field__title">{{ t('ai.defaultOptions') }}</span>
          <v-textarea
            v-model="sourceForm.default_options_json"
            :aria-label="t('ai.defaultOptions')"
            auto-grow
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
            rows="2"
          />
        </label>
        <label class="workbench-field workbench-field--wide">
          <span class="workbench-field__title">{{ t('ai.capabilityProvenance') }}</span>
          <v-textarea
            v-model="sourceForm.capability_provenance_json"
            :aria-label="t('ai.capabilityProvenance')"
            auto-grow
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
            rows="2"
          />
        </label>
        <label class="workbench-field">
          <span class="workbench-field__title">{{ t('ai.sourceTimeoutSeconds') }}</span>
          <v-text-field
            v-model.number="sourceForm.timeout_seconds"
            :aria-label="t('ai.sourceTimeoutSeconds')"
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
            type="number"
          />
        </label>
        <div class="workbench-field workbench-field--switch">
          <span class="workbench-field__title">{{ t('ai.sourceEnabled') }}</span>
          <v-switch
            v-model="sourceForm.enabled"
            :aria-label="t('ai.sourceEnabled')"
            class="workbench-field__control"
            color="primary"
            density="comfortable"
            :disabled="savingSource"
            hide-details
          />
        </div>
        <label class="workbench-field">
          <span class="workbench-field__title">{{ t('ai.sourceProxy') }}</span>
          <v-text-field
            v-model.trim="sourceForm.proxy"
            :aria-label="t('ai.sourceProxy')"
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
          />
        </label>
        <label
          v-if="sourceForm.capability_type === 'embedding'"
          class="workbench-field"
        >
          <span class="workbench-field__title">{{ t('ai.sourceEmbeddingDimensions') }}</span>
          <v-text-field
            v-model.number="sourceForm.embedding_dimensions"
            :aria-label="t('ai.sourceEmbeddingDimensions')"
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
            type="number"
          />
        </label>
        <label
          v-if="sourceForm.capability_type === 'speech_to_text'"
          class="workbench-field"
        >
          <span class="workbench-field__title">{{ t('ai.sourceSttLanguage') }}</span>
          <v-text-field
            v-model.trim="sourceForm.stt_language"
            :aria-label="t('ai.sourceSttLanguage')"
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
          />
        </label>
        <label
          v-if="sourceForm.capability_type === 'text_to_speech'"
          class="workbench-field"
        >
          <span class="workbench-field__title">{{ t('ai.sourceTtsVoice') }}</span>
          <v-text-field
            v-model.trim="sourceForm.tts_voice"
            :aria-label="t('ai.sourceTtsVoice')"
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
          />
        </label>
        <label
          v-if="sourceForm.capability_type === 'text_to_speech'"
          class="workbench-field"
        >
          <span class="workbench-field__title">{{ t('ai.sourceTtsFormat') }}</span>
          <v-select
            v-model="sourceForm.tts_response_format"
            :aria-label="t('ai.sourceTtsFormat')"
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
            :items="ttsResponseFormatOptions"
          />
        </label>
        <label
          v-if="sourceForm.capability_type === 'rerank'"
          class="workbench-field"
        >
          <span class="workbench-field__title">{{ t('ai.sourceRerankApiSuffix') }}</span>
          <v-text-field
            v-model.trim="sourceForm.rerank_api_suffix"
            :aria-label="t('ai.sourceRerankApiSuffix')"
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
          />
        </label>
        <label
          v-if="sourceForm.capability_type === 'rerank'"
          class="workbench-field"
        >
          <span class="workbench-field__title">{{ t('ai.sourceRerankTopN') }}</span>
          <v-text-field
            v-model.number="sourceForm.rerank_top_n"
            :aria-label="t('ai.sourceRerankTopN')"
            class="workbench-field__control"
            density="comfortable"
            :disabled="savingSource"
            hide-details
            type="number"
          />
        </label>
      </div>
    </PopupPanel>
  </v-sheet>
</template>

<script setup lang="ts">
  import type { AISourcePresetItem } from '@/api/ai/types'
  import type { SourceFormState } from '@/composables/aiModels/formState'
  import type {
    AISetupWorkflow,
    AIWorkflowOperationResult,
  } from '@/composables/aiModels/setupWorkflow'
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { PopupPanel } from '@/components/workbench'
  import AIWorkflowResultAlert from './AIWorkflowResultAlert.vue'

  const props = defineProps<{
    canSaveSource: boolean
    deletingSource: boolean
    displayedSourceErrors: {
      name: string
      preset_type: string
    }
    isCreatingSource: boolean
    removeSource: () => void | Promise<void>
    saveSource: () => void | Promise<void>
    savingSource: boolean
    selectSourceProtocol: (presetType: string) => void
    focused?: boolean
    highlight?: string
    sourcePresetInitial: (value: string) => string
    sourcePresetLabel: (value: string) => string
    sourcePresetOptions: Array<{
      title: string
      value: string
    }>
    sourcePresets: AISourcePresetItem[]
    touchSourceField: (field: 'name' | 'preset_type') => void
    workflow: AISetupWorkflow
    workflowResult: AIWorkflowOperationResult | null
  }>()

  const { t } = useI18n()
  const sourceForm = defineModel<SourceFormState>('sourceForm', { required: true })

  const sourceApiKeysDialog = ref(false)
  const sourceAdvancedDialog = ref(false)
  const sourceApiKeyDraft = ref<string[]>([])
  const sourceApiKeyDraftInput = ref('')

  const sourcePrimaryApiKey = computed({
    get: () => sourceForm.value.api_keys[0] ?? '',
    set: value => {
      const nextValue = value.trim()
      const nextKeys = [...sourceForm.value.api_keys]
      if (nextValue) {
        nextKeys[0] = nextValue
      } else {
        nextKeys.splice(0, 1)
      }
      sourceForm.value.api_keys = nextKeys
    },
  })
  const extraSourceApiKeys = computed(() => sourceForm.value.api_keys.slice(1))
  const providerSaveDisabledReason = computed(() => {
    if (props.savingSource || props.canSaveSource) {
      return ''
    }
    if (!sourceForm.value.name.trim()) {
      return t('ai.sourceNameRequired')
    }
    if (!sourceForm.value.preset_type.trim()) {
      return t('ai.sourcePresetRequired')
    }
    return props.displayedSourceErrors.name
      || props.displayedSourceErrors.preset_type
      || t('ai.sourceSaveDisabledNoChanges')
  })
  const ttsResponseFormatOptions = [
    { title: 'wav', value: 'wav' },
    { title: 'mp3', value: 'mp3' },
    { title: 'opus', value: 'opus' },
    { title: 'aac', value: 'aac' },
    { title: 'flac', value: 'flac' },
    { title: 'pcm', value: 'pcm' },
  ]

  function openSourceApiKeysEditor () {
    sourceApiKeyDraft.value = [...sourceForm.value.api_keys]
    sourceApiKeyDraftInput.value = ''
    sourceApiKeysDialog.value = true
  }

  function appendSourceApiKeyDraft () {
    const nextValue = sourceApiKeyDraftInput.value.trim()
    if (!nextValue) {
      return
    }
    sourceApiKeyDraft.value = [...sourceApiKeyDraft.value, nextValue]
    sourceApiKeyDraftInput.value = ''
  }

  function removeSourceApiKeyDraft (index: number) {
    sourceApiKeyDraft.value = sourceApiKeyDraft.value.filter((_, itemIndex) => itemIndex !== index)
  }

  function removeExtraSourceApiKey (index: number) {
    sourceForm.value.api_keys = sourceForm.value.api_keys.filter(
      (_, itemIndex) => itemIndex !== index + 1,
    )
  }

  function applySourceApiKeyDraft () {
    sourceForm.value.api_keys = [...sourceApiKeyDraft.value]
    sourceApiKeysDialog.value = false
  }

  function selectProtocol (presetType: string) {
    props.selectSourceProtocol(presetType)
    props.touchSourceField('preset_type')
  }

  function connectionIssueLabel (issue: AISetupWorkflow['connectionIssues'][number]) {
    return t(`ai.connectionIssue.${issue}`)
  }
</script>

<style scoped>
.source-workspace {
  display: grid;
  gap: 16px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(var(--v-theme-outline-variant), 0.2);
}

.source-workspace--focused {
  border-bottom-color: rgba(var(--v-theme-primary), 0.3);
}

.source-workspace__header {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.source-workspace__heading {
  display: grid;
  min-width: 0;
  gap: 8px;
}

.source-summary-line {
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-size: 0.9rem;
  line-height: 1.6;
}

.source-workflow-step {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.source-workflow-step__text {
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.88rem;
  line-height: 1.5;
}

.source-issue-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-protocol-step {
  display: grid;
  gap: 10px;
  padding: 0 0 14px;
  border-bottom: 1px solid rgba(var(--v-theme-outline-variant), 0.18);
}

.source-protocol-step--focused {
  border-bottom-color: rgba(var(--v-theme-primary), 0.28);
}

.source-protocol-step__header {
  display: flex;
  min-width: 0;
  justify-content: space-between;
  gap: 12px;
}

.source-protocol-step__title {
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.98rem;
  font-weight: 720;
  line-height: 1.35;
}

.source-protocol-step__hint {
  margin-top: 3px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.84rem;
  line-height: 1.5;
}

.source-protocol-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.source-protocol-option {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 9px;
  align-items: center;
  padding: 10px 11px;
  border: 1px solid rgba(var(--v-theme-outline-variant), 0.28);
  border-radius: var(--shape-small);
  background: rgba(var(--v-theme-surface), 0.54);
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition: background-color 160ms ease, border-color 160ms ease;
}

.source-protocol-option:hover {
  border-color: rgba(var(--v-theme-primary), 0.36);
  background: rgba(var(--v-theme-primary), 0.07);
}

.source-protocol-option:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.72);
  outline-offset: 2px;
}

.source-protocol-option--active {
  border-color: rgba(var(--v-theme-primary), 0.52);
  background: rgba(var(--v-theme-primary), 0.1);
}

.source-protocol-option__avatar {
  flex-shrink: 0;
  font-size: 0.78rem;
  font-weight: 760;
}

.source-protocol-option__body {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.source-protocol-option__title {
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.88rem;
  font-weight: 720;
  line-height: 1.35;
}

.source-protocol-option__text {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.8rem;
  line-height: 1.45;
  overflow: hidden;
}

.source-protocol-field__value {
  min-height: 44px;
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-theme-outline-variant), 0.32);
  border-radius: var(--shape-small);
  background: rgba(var(--v-theme-surface), 0.44);
  color: rgba(var(--v-theme-on-surface), 0.82);
  font-size: 0.9rem;
  line-height: 1.45;
}

.disabled-reason {
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 0.82rem;
  line-height: 1.5;
}

.source-config-list {
  display: grid;
  gap: 14px 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.source-config-field--wide {
  grid-column: 1 / -1;
}

.source-api-key-field {
  align-items: end;
}

.source-api-key-field__action {
  min-width: 112px;
}

.source-api-key-field__action--highlighted {
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.34);
}

.source-api-key-inline-list {
  display: grid;
  gap: 8px;
  padding-top: 2px;
}

.source-api-key-inline-item {
  display: grid;
  min-width: 0;
  align-items: center;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid rgba(var(--v-theme-outline-variant), 0.22);
  border-radius: var(--shape-small);
  background: rgba(var(--v-theme-surface), 0.42);
}

.source-api-key-inline-item__value {
  overflow: hidden;
  color: rgba(var(--v-theme-on-surface), 0.78);
  font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.8rem;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  padding-top: 2px;
}

.source-form-actions__primary {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.source-api-key-editor {
  display: grid;
  gap: 20px;
}

.source-api-key-editor__composer {
  align-items: end;
}

.source-api-key-editor__list {
  display: grid;
  gap: 12px;
  max-height: 320px;
  overflow-y: auto;
}

.source-api-key-editor__item {
  align-items: center;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding: 0 4px 12px;
}

.source-api-key-editor__value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 960px) {
  .source-config-list {
    grid-template-columns: 1fr;
  }

  .source-form-actions {
    align-items: stretch;
    flex-direction: column-reverse;
  }

  .source-form-actions__primary {
    justify-content: flex-start;
  }
}

</style>
