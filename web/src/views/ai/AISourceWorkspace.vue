<template>
  <v-sheet class="surface-gradient-card pa-4 mb-4 source-workspace" rounded="lg">
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

    <div class="source-config-list">
      <div class="source-config-row">
        <div class="source-config-row__meta">
          <div class="source-config-row__label">{{ t('ai.sourceName') }}</div>
          <div class="source-config-row__hint">{{ t('ai.sourceConfigNameHint') }}</div>
        </div>
        <v-text-field
          v-model.trim="sourceForm.name"
          class="source-config-row__field"
          density="comfortable"
          :disabled="savingSource"
          :error-messages="displayedSourceErrors.name ? [displayedSourceErrors.name] : []"
          hide-details="auto"
          @blur="touchSourceField('name')"
        />
      </div>

      <div class="source-config-row">
        <div class="source-config-row__meta">
          <div class="source-config-row__label">{{ t('ai.sourcePreset') }}</div>
          <div class="source-config-row__hint">{{ t('ai.sourceConfigPresetHint') }}</div>
        </div>
        <v-select
          v-model="sourceForm.preset_type"
          class="source-config-row__field"
          density="comfortable"
          :disabled="savingSource"
          :error-messages="displayedSourceErrors.preset_type ? [displayedSourceErrors.preset_type] : []"
          hide-details="auto"
          :items="sourcePresetOptions"
          @blur="touchSourceField('preset_type')"
        />
      </div>

      <div class="source-config-row">
        <div class="source-config-row__meta">
          <div class="source-config-row__label">{{ t('ai.sourceApiKey') }}</div>
          <div class="source-config-row__hint">{{ t('ai.sourceConfigApiKeyHint') }}</div>
        </div>
        <div class="source-config-row__field source-api-key-field">
          <v-text-field
            density="comfortable"
            hide-details
            :model-value="sourcePrimaryApiKey"
            readonly
          />
          <v-btn
            class="source-api-key-field__action"
            color="primary"
            variant="tonal"
            @click="openSourceApiKeysEditor"
          >
            {{ t('ai.sourceApiKeyManage') }}
          </v-btn>
        </div>
      </div>

      <div class="source-config-row">
        <div class="source-config-row__meta">
          <div class="source-config-row__label">{{ t('ai.sourceApiBase') }}</div>
          <div class="source-config-row__hint">{{ t('ai.sourceConfigApiBaseHint') }}</div>
        </div>
        <v-text-field
          v-model.trim="sourceForm.api_base"
          class="source-config-row__field"
          density="comfortable"
          :disabled="savingSource"
          hide-details
        />
      </div>
    </div>

    <v-dialog v-model="sourceApiKeysDialog" max-width="760">
      <v-card rounded="xl">
        <v-card-title class="text-h5 pt-6 px-6">
          {{ t('ai.sourceApiKeyManageTitle') }}
        </v-card-title>
        <v-card-text class="px-6">
          <div class="source-api-key-editor">
            <div class="source-api-key-editor__composer">
              <v-text-field
                v-model.trim="sourceApiKeyDraftInput"
                density="comfortable"
                hide-details
                :label="t('ai.sourceApiKeyNew')"
                @keydown.enter.prevent="appendSourceApiKeyDraft"
              />
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

    <v-expansion-panels class="mt-3" variant="accordion">
      <v-expansion-panel>
        <v-expansion-panel-title>{{ t('ai.sourceAdvancedConfig') }}</v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="source-advanced-form pt-2">
            <v-text-field
              v-model.trim="sourceForm.adapter_kind"
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.sourceAdapterKind')"
            />
            <v-textarea
              v-model="sourceForm.capability_metadata_json"
              auto-grow
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.capabilityMetadata')"
              rows="2"
            />
            <v-textarea
              v-model="sourceForm.default_options_json"
              auto-grow
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.defaultOptions')"
              rows="2"
            />
            <v-textarea
              v-model="sourceForm.capability_provenance_json"
              auto-grow
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.capabilityProvenance')"
              rows="2"
            />
            <v-text-field
              v-model.number="sourceForm.timeout_seconds"
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.sourceTimeoutSeconds')"
              type="number"
            />
            <v-switch
              v-model="sourceForm.enabled"
              color="primary"
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.sourceEnabled')"
            />
            <v-text-field
              v-model.trim="sourceForm.proxy"
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.sourceProxy')"
            />
            <v-text-field
              v-if="sourceForm.capability_type === 'embedding'"
              v-model.number="sourceForm.embedding_dimensions"
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.sourceEmbeddingDimensions')"
              type="number"
            />
            <v-text-field
              v-if="sourceForm.capability_type === 'speech_to_text'"
              v-model.trim="sourceForm.stt_language"
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.sourceSttLanguage')"
            />
            <v-text-field
              v-if="sourceForm.capability_type === 'text_to_speech'"
              v-model.trim="sourceForm.tts_voice"
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.sourceTtsVoice')"
            />
            <v-select
              v-if="sourceForm.capability_type === 'text_to_speech'"
              v-model="sourceForm.tts_response_format"
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :items="ttsResponseFormatOptions"
              :label="t('ai.sourceTtsFormat')"
            />
            <v-text-field
              v-if="sourceForm.capability_type === 'rerank'"
              v-model.trim="sourceForm.rerank_api_suffix"
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.sourceRerankApiSuffix')"
            />
            <v-text-field
              v-if="sourceForm.capability_type === 'rerank'"
              v-model.number="sourceForm.rerank_top_n"
              density="comfortable"
              :disabled="savingSource"
              hide-details
              :label="t('ai.sourceRerankTopN')"
              type="number"
            />
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-sheet>
</template>

<script setup lang="ts">
  import type { SourceFormState } from '@/composables/aiModels/formState'
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'

  defineProps<{
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
    sourcePresetLabel: (value: string) => string
    sourcePresetOptions: Array<{
      title: string
      value: string
    }>
    touchSourceField: (field: 'name' | 'preset_type') => void
  }>()

  const { t } = useI18n()
  const sourceForm = defineModel<SourceFormState>('sourceForm', { required: true })

  const sourceApiKeysDialog = ref(false)
  const sourceApiKeyDraft = ref<string[]>([])
  const sourceApiKeyDraftInput = ref('')

  const sourcePrimaryApiKey = computed(() => sourceForm.value.api_keys[0] ?? '')
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
</script>

<style scoped>
.source-workspace {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.source-summary-line {
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-size: 0.9rem;
  line-height: 1.6;
}

.source-config-list {
  display: grid;
  gap: 14px;
}

.source-config-row {
  align-items: center;
  display: grid;
  gap: 20px;
  grid-template-columns: minmax(0, 220px) minmax(0, 1fr);
}

.source-config-row__meta {
  min-width: 0;
}

.source-config-row__label {
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.5;
}

.source-config-row__hint {
  color: rgba(var(--v-theme-on-surface), 0.54);
  font-size: 0.85rem;
  line-height: 1.5;
  margin-top: 4px;
}

.source-config-row__field {
  min-width: 0;
}

.source-api-key-field {
  align-items: center;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto;
}

.source-api-key-field__action {
  min-width: 112px;
}

.source-api-key-editor {
  display: grid;
  gap: 20px;
}

.source-api-key-editor__composer {
  align-items: center;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto;
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

.source-advanced-form {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (max-width: 960px) {
  .source-config-row,
  .source-api-key-field,
  .source-api-key-editor__composer,
  .source-advanced-form {
    grid-template-columns: 1fr;
  }
}
</style>
