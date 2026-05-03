import type {
  AIWorkflowOperationResult,
  AIWorkflowResultStage,
} from './setupWorkflow'
import type {
  AIModelCatalogItem,
  AISourceItem,
  AISourceModelItem,
  AISourcePresetItem,
} from '@/api/ai/types'
import { computed, reactive, ref, type Ref, watch } from 'vue'
import { createAISource, deleteAISource, updateAISource } from '@/api/ai/sources'
import { getErrorMessage } from '@/api/client'
import {
  buildSourceExtraConfig,
  buildSourceSnapshot,
  defaultPresetTypeFor,
  extractOptionalInt,
  extractOptionalString,
  extractSourceApiKeys,
  normalizeApiKeys,
  parseJsonObject,
  resolveSourceCapabilityType,
  type SourceFormState,
  stringifyJsonObject,
} from './formState'

type NoticeLevel = 'error' | 'success' | 'warning'
type SourceTouchedField = 'name' | 'preset_type'
export type AIProviderDetailMode = 'creating' | 'empty' | 'selected'

interface UseAISourceStateOptions {
  sourceCapabilityTab: Readonly<Ref<string>>
  t: (key: string, params?: Record<string, unknown>) => string
  notify: (message: string, level: NoticeLevel) => void
  sourceModels: Ref<AISourceModelItem[]>
  fetchedSourceModels: Ref<AIModelCatalogItem[]>
  loadModelsData: () => Promise<void>
  loadSourceModelsFor: (sourceId: string) => Promise<void>
  reportWorkflowResult: (
    stage: AIWorkflowResultStage,
    result: AIWorkflowOperationResult,
  ) => void
  startCreateSourceModel: () => void
  startCreateModelProfile: () => void
  syncActiveCapabilitySelection: () => Promise<void>
}

export function useAISourceState ({
  sourceCapabilityTab,
  t,
  notify,
  sourceModels,
  fetchedSourceModels,
  loadModelsData,
  loadSourceModelsFor,
  reportWorkflowResult,
  startCreateSourceModel,
  startCreateModelProfile,
  syncActiveCapabilitySelection,
}: UseAISourceStateOptions) {
  const allSourcePresets = ref<AISourcePresetItem[]>([])
  const allSources = ref<AISourceItem[]>([])

  const loadingSources = ref(false)
  const savingSource = ref(false)
  const deletingSource = ref(false)
  const providerDetailMode = ref<AIProviderDetailMode>('empty')

  const sourceBaseline = ref('')
  const sourceSubmitAttempted = ref(false)
  const sourceTouched = reactive<Record<SourceTouchedField, boolean>>({
    name: false,
    preset_type: false,
  })

  const sourceForm = reactive<SourceFormState>({
    source_id: '',
    name: '',
    preset_type: '',
    capability_type: resolveSourceCapabilityType(sourceCapabilityTab.value),
    adapter_kind: 'openai_compatible',
    api_base: '',
    api_keys: [],
    api_key_env_name: '',
    proxy: '',
    enabled: true,
    timeout_seconds: 120,
    embedding_dimensions: null,
    stt_language: '',
    tts_voice: 'alloy',
    tts_response_format: 'wav',
    rerank_api_suffix: '/rerank',
    rerank_top_n: 2,
    capability_metadata_json: '{}',
    default_options_json: '{}',
    capability_provenance_json: '{}',
  })

  const currentSourceCapability = computed(() => (
    resolveSourceCapabilityType(sourceCapabilityTab.value)
  ))
  const sourcePresets = computed(() => allSourcePresets.value.filter(
    item => item.capability_type === currentSourceCapability.value,
  ))
  const sources = computed(() => allSources.value.filter(
    item => item.capability_type === currentSourceCapability.value,
  ))

  const selectedSource = computed(() => (
    sources.value.find(item => item.source_id === sourceForm.source_id) ?? null
  ))
  const selectedSourcePreset = computed(() => (
    sourcePresets.value.find(item => item.preset_type === sourceForm.preset_type)
    ?? null
  ))

  const sourceErrors = computed(() => ({
    name:
      sourceForm.name.trim().length === 0 ? t('ai.sourceNameRequired') : '',
    preset_type:
      sourceForm.preset_type.trim().length === 0
        ? t('ai.sourcePresetRequired')
        : '',
  }))

  const displayedSourceErrors = computed(() => ({
    name:
      sourceTouched.name || sourceSubmitAttempted.value
        ? sourceErrors.value.name
        : '',
    preset_type:
      sourceTouched.preset_type || sourceSubmitAttempted.value
        ? sourceErrors.value.preset_type
        : '',
  }))

  const sourceValid = computed(() => (
    !sourceErrors.value.name && !sourceErrors.value.preset_type
  ))
  const sourceDirty = computed(() => (
    buildSourceSnapshot(sourceForm) !== sourceBaseline.value
  ))
  const isCreatingSource = computed(() => sourceForm.source_id.length === 0)
  const canSaveSource = computed(() => (
    sourceValid.value && sourceDirty.value && !savingSource.value
  ))
  const canFetchSourceModels = computed(() => (
    sourceForm.preset_type.trim().length > 0
    && sourceForm.api_base.trim().length > 0
    && (
      normalizeApiKeys(sourceForm.api_keys).length > 0
      || sourceForm.api_key_env_name.trim().length > 0
    )
  ))

  const normalizedSourceApiKeys = computed(() => (
    normalizeApiKeys(sourceForm.api_keys)
  ))
  const normalizedSourceExtraConfig = computed(() => (
    buildSourceExtraConfig(sourceForm)
  ))

  watch(selectedSourcePreset, preset => {
    if (!preset) {
      return
    }
    sourceForm.capability_type = preset.capability_type
    sourceForm.adapter_kind = preset.adapter_kind
    if (!sourceForm.api_base.trim() && preset.default_api_base) {
      sourceForm.api_base = preset.default_api_base
    }
    if (sourceForm.capability_metadata_json.trim() === '{}') {
      sourceForm.capability_metadata_json = stringifyJsonObject(
        preset.capability_metadata,
      )
    }
    if (sourceForm.default_options_json.trim() === '{}') {
      sourceForm.default_options_json = stringifyJsonObject(preset.default_options)
    }
    if (sourceForm.capability_provenance_json.trim() === '{}') {
      sourceForm.capability_provenance_json = stringifyJsonObject(
        preset.capability_provenance,
      )
    }
  })

  watch(currentSourceCapability, async capability => {
    sourceForm.capability_type = capability
    if (loadingSources.value) {
      return
    }
    await syncActiveCapabilitySelection()
  })

  function resetSourceValidation () {
    sourceSubmitAttempted.value = false
    sourceTouched.name = false
    sourceTouched.preset_type = false
  }

  function syncSourceBaseline () {
    sourceBaseline.value = buildSourceSnapshot(sourceForm)
  }

  function touchSourceField (field: SourceTouchedField) {
    sourceTouched[field] = true
  }

  function clearSourceSelection () {
    providerDetailMode.value = 'empty'
    sourceForm.source_id = ''
    sourceForm.name = ''
    sourceForm.preset_type = ''
    sourceForm.capability_type = currentSourceCapability.value
    sourceForm.adapter_kind = 'openai_compatible'
    sourceForm.api_base = ''
    sourceForm.api_keys = []
    sourceForm.api_key_env_name = ''
    sourceForm.proxy = ''
    sourceForm.enabled = true
    sourceForm.timeout_seconds = 120
    sourceForm.embedding_dimensions = null
    sourceForm.stt_language = ''
    sourceForm.tts_voice = 'alloy'
    sourceForm.tts_response_format = 'wav'
    sourceForm.rerank_api_suffix = '/rerank'
    sourceForm.rerank_top_n = 2
    sourceForm.capability_metadata_json = '{}'
    sourceForm.default_options_json = '{}'
    sourceForm.capability_provenance_json = '{}'
    syncSourceBaseline()
    resetSourceValidation()
    sourceModels.value = []
    fetchedSourceModels.value = []
    startCreateSourceModel()
    startCreateModelProfile()
  }

  async function selectSource (item: AISourceItem) {
    providerDetailMode.value = 'selected'
    sourceForm.source_id = item.source_id
    sourceForm.name = item.name
    sourceForm.preset_type = item.preset_type
    sourceForm.capability_type = item.capability_type
    sourceForm.adapter_kind = item.adapter_kind ?? ''
    sourceForm.api_base = item.api_base ?? ''
    sourceForm.api_keys = extractSourceApiKeys(item)
    sourceForm.api_key_env_name = item.api_key_env_name ?? ''
    sourceForm.proxy = extractOptionalString(item.extra_config?.proxy)
    sourceForm.enabled = item.enabled
    sourceForm.timeout_seconds = item.timeout_seconds
    sourceForm.embedding_dimensions = extractOptionalInt(
      item.extra_config?.embedding_dimensions,
    )
    sourceForm.stt_language = extractOptionalString(
      item.extra_config?.stt_language,
    )
    sourceForm.tts_voice
      = extractOptionalString(item.extra_config?.tts_voice) || 'alloy'
    sourceForm.tts_response_format
      = extractOptionalString(item.extra_config?.tts_response_format) || 'wav'
    sourceForm.rerank_api_suffix
      = extractOptionalString(item.extra_config?.rerank_api_suffix) || '/rerank'
    sourceForm.rerank_top_n
      = extractOptionalInt(item.extra_config?.rerank_top_n) ?? 2
    sourceForm.capability_metadata_json = stringifyJsonObject(
      item.capability_metadata,
    )
    sourceForm.default_options_json = stringifyJsonObject(item.default_options)
    sourceForm.capability_provenance_json = stringifyJsonObject(
      item.capability_provenance,
    )
    syncSourceBaseline()
    resetSourceValidation()
    fetchedSourceModels.value = []
    await loadSourceModelsFor(item.source_id)
  }

  function startCreateSource (presetType?: string) {
    providerDetailMode.value = 'creating'
    const defaultPreset = (
      sourcePresets.value.find(item => item.preset_type === presetType)
      ?? sourcePresets.value[0]
    )
    sourceForm.source_id = ''
    sourceForm.name = ''
    sourceForm.preset_type
      = defaultPreset?.preset_type
        ?? defaultPresetTypeFor(sourceCapabilityTab.value)
    sourceForm.capability_type = currentSourceCapability.value
    sourceForm.adapter_kind = defaultPreset?.adapter_kind ?? 'openai_compatible'
    sourceForm.api_base = defaultPreset?.default_api_base ?? ''
    sourceForm.api_keys = []
    sourceForm.api_key_env_name = ''
    sourceForm.proxy = ''
    sourceForm.enabled = true
    sourceForm.timeout_seconds = 120
    sourceForm.embedding_dimensions = null
    sourceForm.stt_language = ''
    sourceForm.tts_voice = 'alloy'
    sourceForm.tts_response_format = 'wav'
    sourceForm.rerank_api_suffix = '/rerank'
    sourceForm.rerank_top_n = 2
    sourceForm.capability_metadata_json = stringifyJsonObject(
      defaultPreset?.capability_metadata,
    )
    sourceForm.default_options_json = stringifyJsonObject(
      defaultPreset?.default_options,
    )
    sourceForm.capability_provenance_json = stringifyJsonObject(
      defaultPreset?.capability_provenance,
    )
    syncSourceBaseline()
    resetSourceValidation()
    sourceModels.value = []
    fetchedSourceModels.value = []
    startCreateSourceModel()
    startCreateModelProfile()
  }

  async function saveSource () {
    sourceSubmitAttempted.value = true
    if (!sourceValid.value) {
      const message = (
        sourceErrors.value.name
        || sourceErrors.value.preset_type
        || t('ai.sourceSaveFailed')
      )
      reportWorkflowResult('provider', { message, status: 'error' })
      notify(message, 'error')
      return
    }
    if (!sourceDirty.value) {
      return
    }
    savingSource.value = true
    try {
      const payload = {
        source_id: sourceForm.source_id || undefined,
        name: sourceForm.name.trim(),
        preset_type: sourceForm.preset_type,
        capability_type: sourceForm.capability_type,
        api_base: sourceForm.api_base.trim() || null,
        api_key_env_name: sourceForm.api_key_env_name.trim() || null,
        enabled: sourceForm.enabled,
        timeout_seconds: sourceForm.timeout_seconds,
        custom_headers: {},
        extra_config: normalizedSourceExtraConfig.value,
        adapter_kind: sourceForm.adapter_kind.trim() || null,
        capability_metadata: parseJsonObject(sourceForm.capability_metadata_json),
        default_options: parseJsonObject(sourceForm.default_options_json),
        capability_provenance: parseJsonObject(
          sourceForm.capability_provenance_json,
        ),
      }
      const response = sourceForm.source_id
        ? await updateAISource({ ...payload, source_id: sourceForm.source_id })
        : await createAISource(payload)
      if (response.data) {
        await loadModelsData()
        await selectSource(response.data)
      }
      const message = t('ai.sourceSaved')
      reportWorkflowResult('provider', { message, status: 'success' })
      notify(message, 'success')
    } catch (error) {
      const message = getErrorMessage(error, t('ai.sourceSaveFailed'))
      reportWorkflowResult('provider', { message, status: 'error' })
      notify(message, 'error')
    } finally {
      savingSource.value = false
    }
  }

  async function removeSource () {
    if (!sourceForm.source_id) {
      return
    }
    deletingSource.value = true
    try {
      await deleteAISource(sourceForm.source_id)
      await loadModelsData()
      const message = t('ai.sourceDeleted')
      reportWorkflowResult('provider', { message, status: 'success' })
      notify(message, 'success')
    } catch (error) {
      const message = getErrorMessage(error, t('ai.sourceDeleteFailed'))
      reportWorkflowResult('provider', { message, status: 'error' })
      notify(message, 'error')
    } finally {
      deletingSource.value = false
    }
  }

  return {
    allSourcePresets,
    allSources,
    canFetchSourceModels,
    canSaveSource,
    clearSourceSelection,
    currentSourceCapability,
    deletingSource,
    displayedSourceErrors,
    isCreatingSource,
    loadingSources,
    normalizedSourceApiKeys,
    normalizedSourceExtraConfig,
    providerDetailMode,
    removeSource,
    saveSource,
    savingSource,
    selectSource,
    selectedSource,
    sourceForm,
    sourcePresets,
    sources,
    startCreateSource,
    touchSourceField,
  }
}
