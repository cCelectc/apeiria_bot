<template>
  <v-sheet
    class="surface-gradient-card pa-4 mb-4 source-workspace"
    :class="{ 'source-workspace--focused': focused }"
  >
    <div class="source-workflow-step mb-4">
      <v-chip color="primary" size="small" variant="tonal">
        {{ t(focused ? 'ai.setupStep.connection' : 'ai.setupStep.provider') }}
      </v-chip>
      <div class="source-workflow-step__text">
        {{ t(focused ? 'ai.modelFlowStepHint.connection' : 'ai.providerWorkflowHint') }}
      </div>
    </div>

    <div class="d-flex flex-wrap justify-space-between align-start ga-3 mb-4">
      <div>
        <div class="text-h6 font-weight-medium">
          {{ sourceForm.name || t('ai.sourceConfigTitle') }}
        </div>
        <div class="text-body-2 text-medium-emphasis mt-1">
          {{ sourceForm.api_base || (isCreatingSource ? t('ai.sourceCreateHint') : t('ai.sourceConfigHint')) }}
        </div>
        <div class="source-summary-line mt-2">
          <span>{{ t('ai.sourcePreset') }}：</span>
          <strong>{{ sourcePresetLabel(sourceForm.preset_type) }}</strong>
        </div>
      </div>
      <div class="d-flex flex-wrap ga-2">
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

    <div v-if="workflow.connectionIssues.length > 0" class="source-issue-list mb-4">
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
      <div class="source-config-row workbench-field-row">
        <div class="workbench-field-row__meta">
          <div class="workbench-field__title">{{ t('ai.sourceName') }}</div>
          <div class="workbench-field__helper">{{ t('ai.sourceConfigNameHint') }}</div>
        </div>
        <v-text-field
          v-model.trim="sourceForm.name"
          :aria-label="t('ai.sourceName')"
          class="workbench-field-row__control"
          density="comfortable"
          :disabled="savingSource"
          :error-messages="displayedSourceErrors.name ? [displayedSourceErrors.name] : []"
          hide-details="auto"
          @blur="touchSourceField('name')"
        />
      </div>

      <div class="source-config-row workbench-field-row">
        <div class="workbench-field-row__meta">
          <div class="workbench-field__title">{{ t('ai.sourcePreset') }}</div>
          <div class="workbench-field__helper">{{ t('ai.sourceConfigPresetHint') }}</div>
        </div>
        <v-select
          v-model="sourceForm.preset_type"
          :aria-label="t('ai.sourcePreset')"
          class="workbench-field-row__control"
          density="comfortable"
          :disabled="savingSource"
          :error-messages="displayedSourceErrors.preset_type ? [displayedSourceErrors.preset_type] : []"
          hide-details="auto"
          :items="sourcePresetOptions"
          @blur="touchSourceField('preset_type')"
        />
      </div>

      <div class="source-config-row workbench-field-row">
        <div class="workbench-field-row__meta">
          <div class="workbench-field__title">{{ t('ai.sourceApiKey') }}</div>
          <div class="workbench-field__helper">{{ t('ai.sourceConfigApiKeyHint') }}</div>
        </div>
        <div class="workbench-field-row__control source-api-key-field workbench-field-action-row">
          <v-text-field
            :aria-label="t('ai.sourceApiKey')"
            density="comfortable"
            hide-details
            :model-value="sourcePrimaryApiKey"
            readonly
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
      </div>

      <div class="source-config-row workbench-field-row">
        <div class="workbench-field-row__meta">
          <div class="workbench-field__title">{{ t('ai.sourceApiBase') }}</div>
          <div class="workbench-field__helper">{{ t('ai.sourceConfigApiBaseHint') }}</div>
        </div>
        <v-text-field
          v-model.trim="sourceForm.api_base"
          :aria-label="t('ai.sourceApiBase')"
          class="workbench-field-row__control"
          density="comfortable"
          :disabled="savingSource"
          hide-details
        />
      </div>
    </div>

    <div v-if="providerSaveDisabledReason" class="disabled-reason mt-3">
      {{ providerSaveDisabledReason }}
    </div>
    <AIWorkflowResultAlert :result="workflowResult" />

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

    <div class="source-secondary-actions mt-3">
      <v-btn prepend-icon="mdi-tune-variant" variant="tonal" @click="sourceAdvancedDialog = true">
        {{ t('ai.sourceAdvancedConfigAction') }}
      </v-btn>
    </div>

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
    focused?: boolean
    highlight?: string
    sourcePresetLabel: (value: string) => string
    sourcePresetOptions: Array<{
      title: string
      value: string
    }>
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

  const sourcePrimaryApiKey = computed(() => sourceForm.value.api_keys[0] ?? '')
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

  function applySourceApiKeyDraft () {
    sourceForm.value.api_keys = [...sourceApiKeyDraft.value]
    sourceApiKeysDialog.value = false
  }

  function connectionIssueLabel (issue: AISetupWorkflow['connectionIssues'][number]) {
    return t(`ai.connectionIssue.${issue}`)
  }
</script>

<style scoped>
.source-workspace {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.source-workspace--focused {
  border-color: rgba(var(--v-theme-primary), 0.38);
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.12);
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

.disabled-reason {
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 0.82rem;
  line-height: 1.5;
}

.source-config-list {
  display: grid;
  gap: 14px;
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

.source-secondary-actions {
  display: flex;
  justify-content: flex-end;
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

</style>
