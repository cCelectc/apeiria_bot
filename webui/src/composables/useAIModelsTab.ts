import type {
  AIModelBindingItem,
  AIModelCatalogItem,
  AIModelProfileItem,
  AISourceItem,
  AISourceModelItem,
  AISourcePresetItem,
} from '@/api/ai'
import { computed, reactive, ref, type Ref, watch } from 'vue'
import {
  createAISource,
  createAISourceModel,
  deleteAISource,
  deleteAISourceModel,
  fetchAISourceModels,
  getAIModelBindings,
  getAIModelProfiles,
  getAISourceModels,
  getAISourcePresets,
  getAISources,
  testAISourceModel,
  updateAISource,
  updateAISourceModel,
  upsertAIModelProfile,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'
import {
  buildModelSnapshot,
  buildProfileSnapshot,
  buildSourceExtraConfig,
  buildSourceSnapshot,
  extractOptionalInt,
  extractOptionalString,
  extractSourceApiKeys,
  normalizeApiKeys,
  parseJsonObject,
  resolveSourceCapabilityType,
  stringifyJsonObject,
  type ModelFormState,
  type ProfileFormState,
  type SourceFormState,
} from '@/composables/aiModels/formState'
import {
  deriveAISetupWorkflow,
  type AIWorkflowOperationResult,
  type AIWorkflowResultStage,
} from '@/utils/aiSetupWorkflow'

type NoticeLevel = 'error' | 'success' | 'warning'
type SourceTouchedField = 'name' | 'preset_type'
type ModelTouchedField = 'display_name' | 'model_identifier'
type ProfileTouchedField = 'model_id' | 'name'

export type AIProviderDetailMode = 'creating' | 'empty' | 'selected'

const taskClassValues = [
  'reply_default',
  'reply_roleplay',
  'tool_orchestration',
  'memory_extraction',
  'planner_light',
  'reasoning_heavy',
]

export function useAIModelsTab(
  sourceCapabilityTab: Readonly<Ref<string>>,
  t: (key: string, params?: Record<string, unknown>) => string,
) {
  const noticeStore = useNoticeStore()
  const allSourcePresets = ref<AISourcePresetItem[]>([])
  const allSources = ref<AISourceItem[]>([])
  const sourceModels = ref<AISourceModelItem[]>([])
  const fetchedSourceModels = ref<AIModelCatalogItem[]>([])
  const modelProfiles = ref<AIModelProfileItem[]>([])
  const modelBindings = ref<AIModelBindingItem[]>([])

  const loadingSources = ref(false)
  const loadingSourceModels = ref(false)
  const savingSource = ref(false)
  const deletingSource = ref(false)
  const fetchingSourceModels = ref(false)
  const savingModel = ref(false)
  const importingModelIdentifier = ref('')
  const testingModelIdentifier = ref('')
  const deletingModelId = ref('')
  const savingProfile = ref(false)
  const providerDetailMode = ref<AIProviderDetailMode>('empty')

  const sourceBaseline = ref('')
  const modelBaseline = ref('')
  const profileBaseline = ref('')
  const sourceSubmitAttempted = ref(false)
  const modelSubmitAttempted = ref(false)
  const profileSubmitAttempted = ref(false)

  const sourceTouched = reactive<Record<SourceTouchedField, boolean>>({
    name: false,
    preset_type: false,
  })
  const modelTouched = reactive<Record<ModelTouchedField, boolean>>({
    display_name: false,
    model_identifier: false,
  })
  const profileTouched = reactive<Record<ProfileTouchedField, boolean>>({
    model_id: false,
    name: false,
  })

  const workflowResults = reactive<Record<AIWorkflowResultStage, AIWorkflowOperationResult | null>>({
    discovery: null,
    model: null,
    profile: null,
    provider: null,
    validation: null,
  })

  const sourceForm = reactive<SourceFormState>({
    adapter_kind: 'openai_compatible',
    api_base: '',
    api_key_action: 'replace',
    api_key_metadata: [],
    api_keys: [],
    capability_metadata_json: '{}',
    capability_provenance_json: '{}',
    capability_type: resolveSourceCapabilityType(sourceCapabilityTab.value),
    default_options_json: '{}',
    embedding_dimensions: null,
    enabled: true,
    name: '',
    preset_type: '',
    proxy: '',
    rerank_api_suffix: '/rerank',
    rerank_top_n: 2,
    source_id: '',
    stt_language: '',
    timeout_seconds: 120,
    tts_response_format: 'wav',
    tts_voice: 'alloy',
  })

  const modelForm = reactive<ModelFormState>({
    capability_metadata_json: '{}',
    capability_provenance_json: '{}',
    default_options_json: '{}',
    display_name: '',
    enabled: true,
    is_default: false,
    model_id: '',
    model_identifier: '',
    source_id: '',
  })

  const profileForm = reactive<ProfileFormState>({
    enabled: true,
    fallback_profile_id: '',
    model_id: '',
    name: '',
    priority: 100,
    profile_id: '',
    task_class: 'reply_default',
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
  const isCreatingSource = computed(() => sourceForm.source_id.length === 0)
  const isCreatingModel = computed(() => modelForm.model_id.length === 0)
  const isChatCapability = computed(() => (
    currentSourceCapability.value === 'chat_completion'
  ))
  const configuredSourceModelIds = computed(() => (
    new Set(sourceModels.value.map(item => item.model_id))
  ))
  const filteredModelProfiles = computed(() => modelProfiles.value.filter(
    item => configuredSourceModelIds.value.has(item.model_id),
  ))
  const modelProfileCount = computed(() => filteredModelProfiles.value.length)
  const isCreatingProfile = computed(() => profileForm.profile_id.length === 0)

  const sourceErrors = computed(() => ({
    name: sourceForm.name.trim().length === 0 ? t('ai.sourceNameRequired') : '',
    preset_type: sourceForm.preset_type.trim().length === 0
      ? t('ai.sourcePresetRequired')
      : '',
  }))
  const displayedSourceErrors = computed(() => ({
    name: sourceTouched.name || sourceSubmitAttempted.value
      ? sourceErrors.value.name
      : '',
    preset_type: sourceTouched.preset_type || sourceSubmitAttempted.value
      ? sourceErrors.value.preset_type
      : '',
  }))
  const sourceValid = computed(() => (
    !sourceErrors.value.name && !sourceErrors.value.preset_type
  ))
  const sourceDirty = computed(() => (
    buildSourceSnapshot(sourceForm) !== sourceBaseline.value
  ))
  const canSaveSource = computed(() => (
    sourceValid.value && sourceDirty.value && !savingSource.value
  ))
  const normalizedSourceApiKeys = computed(() => normalizeApiKeys(sourceForm.api_keys))
  const sourceHasApiKey = computed(() => (
    sourceForm.api_key_action !== 'clear'
    && (
      normalizedSourceApiKeys.value.length > 0
      || sourceForm.api_key_metadata.length > 0
    )
  ))
  const normalizedSourceExtraConfig = computed(() => buildSourceExtraConfig(sourceForm))
  const canFetchSourceModels = computed(() => (
    sourceForm.preset_type.trim().length > 0
    && sourceForm.api_base.trim().length > 0
    && sourceHasApiKey.value
    && !fetchingSourceModels.value
  ))

  const modelErrors = computed(() => ({
    display_name: modelForm.display_name.trim().length === 0
      ? t('ai.modelDisplayNameRequired')
      : '',
    model_identifier: modelForm.model_identifier.trim().length === 0
      ? t('ai.modelIdentifierRequired')
      : '',
  }))
  const displayedModelErrors = computed(() => ({
    display_name: modelTouched.display_name || modelSubmitAttempted.value
      ? modelErrors.value.display_name
      : '',
    model_identifier: modelTouched.model_identifier || modelSubmitAttempted.value
      ? modelErrors.value.model_identifier
      : '',
  }))
  const modelValid = computed(() => (
    !modelErrors.value.display_name && !modelErrors.value.model_identifier
  ))
  const modelDirty = computed(() => (
    buildModelSnapshot(modelForm) !== modelBaseline.value
  ))
  const canSaveModel = computed(() => (
    modelValid.value
    && modelDirty.value
    && sourceForm.source_id.length > 0
    && !savingModel.value
  ))

  const profileErrors = computed(() => ({
    model_id: profileForm.model_id.trim().length === 0
      ? t('ai.modelProfileModelRequired')
      : '',
    name: profileForm.name.trim().length === 0
      ? t('ai.modelProfileNameRequired')
      : '',
  }))
  const displayedProfileErrors = computed(() => ({
    model_id: profileTouched.model_id || profileSubmitAttempted.value
      ? profileErrors.value.model_id
      : '',
    name: profileTouched.name || profileSubmitAttempted.value
      ? profileErrors.value.name
      : '',
  }))
  const profileValid = computed(() => (
    !profileErrors.value.model_id && !profileErrors.value.name
  ))
  const profileDirty = computed(() => (
    buildProfileSnapshot(profileForm) !== profileBaseline.value
  ))
  const canSaveProfile = computed(() => (
    isChatCapability.value
    && profileValid.value
    && profileDirty.value
    && !savingProfile.value
  ))

  const profileModelOptions = computed(() => sourceModels.value.map(item => ({
    title: item.display_name,
    value: item.model_id,
  })))
  const fallbackProfileOptions = computed(() => filteredModelProfiles.value
    .filter(item => item.profile_id !== profileForm.profile_id)
    .map(item => ({
      title: item.name,
      value: item.profile_id,
    })))
  const taskClassOptions = computed(() => taskClassValues.map(value => ({
    title: taskClassTitle(value),
    value,
  })))
  const selectedModelBindingCount = computed(() => (
    modelBindings.value.filter(item => item.profile_id === profileForm.profile_id).length
  ))
  const setupWorkflow = computed(() => deriveAISetupWorkflow({
    canFetchSourceModels: canFetchSourceModels.value,
    canSaveModel: canSaveModel.value,
    canSaveProfile: canSaveProfile.value,
    canSaveSource: canSaveSource.value,
    capabilityType: currentSourceCapability.value,
    fetchedSourceModelCount: fetchedSourceModels.value.length,
    modelProfiles: modelProfiles.value,
    selectedSource: sourceForm.source_id
      ? {
          api_base: sourceForm.api_base,
          api_key_configured: sourceHasApiKey.value,
          api_keys: normalizedSourceApiKeys.value,
          enabled: sourceForm.enabled,
          name: sourceForm.name,
          preset_type: sourceForm.preset_type,
          source_id: sourceForm.source_id,
        }
      : null,
    sourceCount: sources.value.length,
    sourceModels: sourceModels.value,
  }))

  function notify(message: string, level: NoticeLevel) {
    noticeStore.show(message, level)
  }

  function taskClassTitle(value: string) {
    const titleMap: Record<string, string> = {
      memory_extraction: 'ai.modelTaskClassMemoryExtraction',
      planner_light: 'ai.modelTaskClassPlannerLight',
      reasoning_heavy: 'ai.modelTaskClassReasoningHeavy',
      reply_default: 'ai.modelTaskClassReplyDefault',
      reply_roleplay: 'ai.modelTaskClassReplyRoleplay',
      tool_orchestration: 'ai.modelTaskClassToolOrchestration',
    }
    return t(titleMap[value] ?? value)
  }

  function reportWorkflowResult(
    stage: AIWorkflowResultStage,
    result: AIWorkflowOperationResult,
  ) {
    workflowResults[stage] = result
  }

  function clearWorkflowResults(...stages: AIWorkflowResultStage[]) {
    const targetStages = stages.length > 0
      ? stages
      : Object.keys(workflowResults) as AIWorkflowResultStage[]
    for (const stage of targetStages) {
      workflowResults[stage] = null
    }
  }

  function resetSourceValidation() {
    sourceSubmitAttempted.value = false
    sourceTouched.name = false
    sourceTouched.preset_type = false
  }

  function resetModelValidation() {
    modelSubmitAttempted.value = false
    modelTouched.display_name = false
    modelTouched.model_identifier = false
  }

  function resetProfileValidation() {
    profileSubmitAttempted.value = false
    profileTouched.model_id = false
    profileTouched.name = false
  }

  function syncSourceBaseline() {
    sourceBaseline.value = buildSourceSnapshot(sourceForm)
  }

  function syncModelBaseline() {
    modelBaseline.value = buildModelSnapshot(modelForm)
  }

  function syncProfileBaseline() {
    profileBaseline.value = buildProfileSnapshot(profileForm)
  }

  function touchSourceField(field: SourceTouchedField) {
    sourceTouched[field] = true
  }

  function touchModelField(field: ModelTouchedField) {
    modelTouched[field] = true
  }

  function touchProfileField(field: ProfileTouchedField) {
    profileTouched[field] = true
  }

  function selectSourceProtocol(presetType: string) {
    const preset = sourcePresets.value.find(item => item.preset_type === presetType)
    sourceForm.preset_type = presetType
    if (!preset) {
      return
    }
    sourceForm.capability_type = preset.capability_type
    sourceForm.adapter_kind = preset.adapter_kind
    sourceForm.capability_metadata_json = stringifyJsonObject(preset.capability_metadata)
    sourceForm.default_options_json = stringifyJsonObject(preset.default_options)
    sourceForm.capability_provenance_json = stringifyJsonObject(preset.capability_provenance)
    sourceTouched.preset_type = true
  }

  function clearSourceSelection() {
    providerDetailMode.value = 'empty'
    Object.assign(sourceForm, {
      adapter_kind: 'openai_compatible',
      api_base: '',
      api_key_action: 'replace',
      api_key_metadata: [],
      api_keys: [],
      capability_metadata_json: '{}',
      capability_provenance_json: '{}',
      capability_type: currentSourceCapability.value,
      default_options_json: '{}',
      embedding_dimensions: null,
      enabled: true,
      name: '',
      preset_type: '',
      proxy: '',
      rerank_api_suffix: '/rerank',
      rerank_top_n: 2,
      source_id: '',
      stt_language: '',
      timeout_seconds: 120,
      tts_response_format: 'wav',
      tts_voice: 'alloy',
    })
    syncSourceBaseline()
    resetSourceValidation()
    sourceModels.value = []
    fetchedSourceModels.value = []
    startCreateSourceModel()
    startCreateModelProfile()
  }

  async function selectSource(item: AISourceItem) {
    providerDetailMode.value = 'selected'
    Object.assign(sourceForm, {
      adapter_kind: item.adapter_kind ?? '',
      api_base: item.api_base ?? '',
      api_key_action: 'keep',
      api_key_metadata: item.api_key_metadata,
      api_keys: extractSourceApiKeys(item),
      capability_metadata_json: stringifyJsonObject(item.capability_metadata),
      capability_provenance_json: stringifyJsonObject(item.capability_provenance),
      capability_type: item.capability_type,
      default_options_json: stringifyJsonObject(item.default_options),
      embedding_dimensions: extractOptionalInt(item.extra_config?.embedding_dimensions),
      enabled: item.enabled,
      name: item.name,
      preset_type: item.preset_type,
      proxy: extractOptionalString(item.extra_config?.proxy),
      rerank_api_suffix: extractOptionalString(item.extra_config?.rerank_api_suffix) || '/rerank',
      rerank_top_n: extractOptionalInt(item.extra_config?.rerank_top_n) ?? 2,
      source_id: item.source_id,
      stt_language: extractOptionalString(item.extra_config?.stt_language),
      timeout_seconds: item.timeout_seconds,
      tts_response_format: extractOptionalString(item.extra_config?.tts_response_format) || 'wav',
      tts_voice: extractOptionalString(item.extra_config?.tts_voice) || 'alloy',
    })
    syncSourceBaseline()
    resetSourceValidation()
    fetchedSourceModels.value = []
    await loadSourceModelsFor(item.source_id)
  }

  function startCreateSource(presetType?: string) {
    providerDetailMode.value = 'creating'
    Object.assign(sourceForm, {
      adapter_kind: 'openai_compatible',
      api_base: '',
      api_key_action: 'replace',
      api_key_metadata: [],
      api_keys: [],
      capability_metadata_json: '{}',
      capability_provenance_json: '{}',
      capability_type: currentSourceCapability.value,
      default_options_json: '{}',
      embedding_dimensions: null,
      enabled: true,
      name: '',
      preset_type: '',
      proxy: '',
      rerank_api_suffix: '/rerank',
      rerank_top_n: 2,
      source_id: '',
      stt_language: '',
      timeout_seconds: 120,
      tts_response_format: 'wav',
      tts_voice: 'alloy',
    })
    syncSourceBaseline()
    resetSourceValidation()
    if (presetType) {
      selectSourceProtocol(presetType)
    }
    sourceModels.value = []
    fetchedSourceModels.value = []
    startCreateSourceModel()
    startCreateModelProfile()
  }

  function selectSourceModel(item: AISourceModelItem) {
    Object.assign(modelForm, {
      capability_metadata_json: stringifyJsonObject(item.capability_metadata),
      capability_provenance_json: stringifyJsonObject(item.capability_provenance),
      default_options_json: stringifyJsonObject(item.default_options),
      display_name: item.display_name,
      enabled: item.enabled,
      is_default: item.is_default,
      model_id: item.model_id,
      model_identifier: item.model_identifier,
      source_id: item.source_id,
    })
    syncModelBaseline()
    resetModelValidation()
  }

  function startCreateSourceModel() {
    Object.assign(modelForm, {
      capability_metadata_json: '{}',
      capability_provenance_json: '{}',
      default_options_json: '{}',
      display_name: '',
      enabled: true,
      is_default: sourceModels.value.length === 0,
      model_id: '',
      model_identifier: '',
      source_id: sourceForm.source_id,
    })
    syncModelBaseline()
    resetModelValidation()
  }

  function selectModelProfile(item: AIModelProfileItem) {
    Object.assign(profileForm, {
      enabled: item.enabled,
      fallback_profile_id: item.fallback_profile_id ?? '',
      model_id: item.model_id,
      name: item.name,
      priority: item.priority,
      profile_id: item.profile_id,
      task_class: item.task_class,
    })
    syncProfileBaseline()
    resetProfileValidation()
  }

  function startCreateModelProfile() {
    Object.assign(profileForm, {
      enabled: true,
      fallback_profile_id: '',
      model_id: sourceModels.value[0]?.model_id ?? '',
      name: '',
      priority: 100,
      profile_id: '',
      task_class: 'reply_default',
    })
    syncProfileBaseline()
    resetProfileValidation()
  }

  function syncActiveProfileSelection() {
    if (!isChatCapability.value) {
      startCreateModelProfile()
      return
    }
    const current = filteredModelProfiles.value.find(
      item => item.profile_id === profileForm.profile_id,
    )
    if (current) {
      selectModelProfile(current)
      return
    }
    if (filteredModelProfiles.value.length > 0) {
      selectModelProfile(filteredModelProfiles.value[0])
      return
    }
    startCreateModelProfile()
  }

  async function loadSourceModelsFor(sourceId: string) {
    if (!sourceId) {
      sourceModels.value = []
      syncActiveProfileSelection()
      startCreateSourceModel()
      return
    }
    loadingSourceModels.value = true
    try {
      const response = await getAISourceModels(sourceId)
      sourceModels.value = response.data
      syncActiveProfileSelection()
      if (!modelForm.model_id && sourceModels.value.length > 0) {
        selectSourceModel(sourceModels.value[0])
      } else if (sourceModels.value.length === 0) {
        startCreateSourceModel()
      }
    } catch (error) {
      notify(getErrorMessage(error, t('ai.modelLoadFailed')), 'error')
    } finally {
      loadingSourceModels.value = false
    }
  }

  async function syncActiveCapabilitySelection() {
    if (providerDetailMode.value === 'creating') {
      return
    }
    const current = sources.value.find(item => item.source_id === sourceForm.source_id)
    if (current) {
      await selectSource(current)
      return
    }
    if (sources.value.length > 0) {
      await selectSource(sources.value[0])
      return
    }
    clearSourceSelection()
  }

  async function loadModelsData() {
    loadingSources.value = true
    try {
      const [presetsResponse, sourcesResponse, profilesResponse, bindingsResponse] = await Promise.all([
        getAISourcePresets(),
        getAISources(),
        getAIModelProfiles(),
        getAIModelBindings(),
      ])
      allSourcePresets.value = presetsResponse.data
      allSources.value = sourcesResponse.data
      modelProfiles.value = profilesResponse.data
      modelBindings.value = bindingsResponse.data
      await syncActiveCapabilitySelection()
    } catch (error) {
      notify(getErrorMessage(error, t('ai.sourceLoadFailed')), 'error')
      throw error
    } finally {
      loadingSources.value = false
    }
  }

  async function saveSource() {
    sourceSubmitAttempted.value = true
    if (!sourceValid.value) {
      const message = sourceErrors.value.name
        || sourceErrors.value.preset_type
        || t('ai.sourceSaveFailed')
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
        adapter_kind: sourceForm.adapter_kind.trim() || null,
        api_base: sourceForm.api_base.trim() || null,
        capability_metadata: parseJsonObject(sourceForm.capability_metadata_json),
        capability_provenance: parseJsonObject(sourceForm.capability_provenance_json),
        capability_type: sourceForm.capability_type,
        custom_headers: {},
        default_options: parseJsonObject(sourceForm.default_options_json),
        enabled: sourceForm.enabled,
        extra_config: normalizedSourceExtraConfig.value,
        api_key_action: sourceForm.api_key_action,
        api_keys: sourceForm.api_key_action === 'replace'
          ? normalizedSourceApiKeys.value
          : [],
        name: sourceForm.name.trim(),
        preset_type: sourceForm.preset_type,
        timeout_seconds: sourceForm.timeout_seconds,
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

  async function removeSource() {
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

  async function saveSourceModel() {
    modelSubmitAttempted.value = true
    if (!modelValid.value) {
      const message = modelErrors.value.model_identifier
        || modelErrors.value.display_name
        || t('ai.modelSaveFailed')
      reportWorkflowResult('model', { message, status: 'error' })
      notify(message, 'error')
      return
    }
    if (!modelDirty.value) {
      return
    }
    savingModel.value = true
    try {
      const payload = {
        capability_metadata: parseJsonObject(modelForm.capability_metadata_json),
        capability_provenance: parseJsonObject(modelForm.capability_provenance_json),
        default_options: parseJsonObject(modelForm.default_options_json),
        display_name: modelForm.display_name.trim(),
        enabled: modelForm.enabled,
        extra_params: {},
        is_default: modelForm.is_default,
        model_identifier: modelForm.model_identifier.trim(),
        source_id: sourceForm.source_id,
      }
      const response = modelForm.model_id
        ? await updateAISourceModel({ ...payload, model_id: modelForm.model_id })
        : await createAISourceModel(payload)
      if (response.data) {
        await loadSourceModelsFor(sourceForm.source_id)
        selectSourceModel(response.data)
      }
      const message = t('ai.modelSaved')
      reportWorkflowResult('model', { message, status: 'success' })
      notify(message, 'success')
    } catch (error) {
      const message = getErrorMessage(error, t('ai.modelSaveFailed'))
      reportWorkflowResult('model', { message, status: 'error' })
      notify(message, 'error')
    } finally {
      savingModel.value = false
    }
  }

  async function removeSourceModel(modelId: string) {
    deletingModelId.value = modelId
    try {
      await deleteAISourceModel(modelId, sourceForm.source_id || undefined)
      await loadSourceModelsFor(sourceForm.source_id)
      const message = t('ai.modelDeleted')
      reportWorkflowResult('model', { message, status: 'success' })
      notify(message, 'success')
    } catch (error) {
      const message = getErrorMessage(error, t('ai.modelDeleteFailed'))
      reportWorkflowResult('model', { message, status: 'error' })
      notify(message, 'error')
    } finally {
      deletingModelId.value = ''
    }
  }

  async function importSourceModelCatalogItem(item: AIModelCatalogItem) {
    if (!sourceForm.source_id || importingModelIdentifier.value) {
      return
    }
    importingModelIdentifier.value = item.id
    try {
      const response = await createAISourceModel({
        capability_metadata: item.capability_metadata,
        capability_provenance: item.capability_provenance,
        default_options: item.default_options,
        display_name: item.name,
        enabled: true,
        extra_params: {},
        is_default: sourceModels.value.length === 0,
        model_identifier: item.id,
        source_id: sourceForm.source_id,
      })
      if (response.data) {
        await loadSourceModelsFor(sourceForm.source_id)
        fetchedSourceModels.value = fetchedSourceModels.value.filter(
          current => current.id !== item.id,
        )
      }
      const message = t('ai.modelSaved')
      reportWorkflowResult('model', {
        detail: item.name || item.id,
        message,
        status: 'success',
      })
      notify(message, 'success')
    } catch (error) {
      const message = getErrorMessage(error, t('ai.modelSaveFailed'))
      reportWorkflowResult('model', { message, status: 'error' })
      notify(message, 'error')
    } finally {
      importingModelIdentifier.value = ''
    }
  }

  async function pullSourceModels() {
    if (!canFetchSourceModels.value || fetchingSourceModels.value) {
      return
    }
    fetchingSourceModels.value = true
    try {
      const response = await fetchAISourceModels({
        api_base: sourceForm.api_base.trim(),
        api_key: normalizedSourceApiKeys.value[0] || null,
        extra_config: normalizedSourceExtraConfig.value,
        preset_type: sourceForm.preset_type,
        source_id: sourceForm.source_id || null,
      })
      fetchedSourceModels.value = response.data
      const message = response.data.length > 0
        ? t('ai.modelsFetched')
        : t('ai.modelFetchEmpty')
      const status = response.data.length > 0 ? 'success' : 'warning'
      reportWorkflowResult('discovery', {
        detail: String(response.data.length),
        message,
        status,
      })
      notify(message, status)
    } catch (error) {
      const message = getErrorMessage(error, t('ai.modelFetchFailed'))
      reportWorkflowResult('discovery', { message, status: 'error' })
      notify(message, 'error')
    } finally {
      fetchingSourceModels.value = false
    }
  }

  async function testSourceModel(modelIdentifier: string) {
    const resolvedModelIdentifier = modelIdentifier.trim()
    if (!resolvedModelIdentifier || testingModelIdentifier.value) {
      return
    }
    testingModelIdentifier.value = resolvedModelIdentifier
    try {
      const response = await testAISourceModel({
        api_base: sourceForm.api_base.trim(),
        api_key: normalizedSourceApiKeys.value[0] || null,
        extra_config: normalizedSourceExtraConfig.value,
        model_identifier: resolvedModelIdentifier,
        preset_type: sourceForm.preset_type,
        source_id: sourceForm.source_id || null,
      })
      const output = response.data.content.trim()
      const message = output
        ? t('ai.modelTestSucceededWithOutput', { output })
        : t('ai.modelTestSucceeded')
      reportWorkflowResult('validation', {
        detail: output,
        message: t('ai.modelTestSucceeded'),
        status: 'success',
      })
      notify(message, 'success')
    } catch (error) {
      const message = getErrorMessage(error, t('ai.modelTestFailed'))
      reportWorkflowResult('validation', { message, status: 'error' })
      notify(message, 'error')
    } finally {
      testingModelIdentifier.value = ''
    }
  }

  async function saveModelProfile() {
    profileSubmitAttempted.value = true
    if (!profileValid.value) {
      const message = profileErrors.value.name
        || profileErrors.value.model_id
        || t('ai.modelProfileSaveFailed')
      reportWorkflowResult('profile', { message, status: 'error' })
      notify(message, 'error')
      return
    }
    if (!profileDirty.value) {
      return
    }
    savingProfile.value = true
    try {
      const response = await upsertAIModelProfile({
        enabled: profileForm.enabled,
        fallback_profile_id: profileForm.fallback_profile_id || null,
        model_id: profileForm.model_id,
        name: profileForm.name.trim(),
        priority: profileForm.priority,
        profile_id: profileForm.profile_id || null,
        task_class: profileForm.task_class,
      })
      if (response.data) {
        const profilesResponse = await getAIModelProfiles()
        modelProfiles.value = profilesResponse.data
        selectModelProfile(response.data)
      }
      const message = t('ai.modelProfileSaved')
      reportWorkflowResult('profile', { message, status: 'success' })
      notify(message, 'success')
    } catch (error) {
      const message = getErrorMessage(error, t('ai.modelProfileSaveFailed'))
      reportWorkflowResult('profile', { message, status: 'error' })
      notify(message, 'error')
    } finally {
      savingProfile.value = false
    }
  }

  watch(selectedSourcePreset, preset => {
    if (!preset) {
      return
    }
    sourceForm.capability_type = preset.capability_type
    sourceForm.adapter_kind = preset.adapter_kind
    if (sourceForm.capability_metadata_json.trim() === '{}') {
      sourceForm.capability_metadata_json = stringifyJsonObject(preset.capability_metadata)
    }
    if (sourceForm.default_options_json.trim() === '{}') {
      sourceForm.default_options_json = stringifyJsonObject(preset.default_options)
    }
    if (sourceForm.capability_provenance_json.trim() === '{}') {
      sourceForm.capability_provenance_json = stringifyJsonObject(preset.capability_provenance)
    }
  })

  watch(currentSourceCapability, async capability => {
    sourceForm.capability_type = capability
    if (!loadingSources.value) {
      await syncActiveCapabilitySelection()
    }
  })

  watch(() => [
    sourceCapabilityTab.value,
    sourceForm.source_id,
  ], () => {
    clearWorkflowResults()
  })

  return {
    canFetchSourceModels,
    canSaveModel,
    canSaveProfile,
    canSaveSource,
    clearWorkflowResults,
    deletingModelId,
    deletingSource,
    displayedModelErrors,
    displayedProfileErrors,
    displayedSourceErrors,
    fallbackProfileOptions,
    fetchedSourceModels,
    fetchingSourceModels,
    filteredModelProfiles,
    importSourceModelCatalogItem,
    importingModelIdentifier,
    isChatCapability,
    isCreatingModel,
    isCreatingProfile,
    isCreatingSource,
    loadModelsData,
    loadingSourceModels,
    loadingSources,
    modelBindings,
    modelForm,
    modelProfileCount,
    modelProfiles,
    profileForm,
    profileModelOptions,
    providerDetailMode,
    pullSourceModels,
    removeSource,
    removeSourceModel,
    saveModelProfile,
    saveSource,
    saveSourceModel,
    savingModel,
    savingProfile,
    savingSource,
    selectModelProfile,
    selectSource,
    selectSourceModel,
    selectSourceProtocol,
    selectedModelBindingCount,
    selectedSource,
    setupWorkflow,
    sourceForm,
    sourceModels,
    sourcePresets,
    sources,
    startCreateModelProfile,
    startCreateSource,
    startCreateSourceModel,
    taskClassOptions,
    testSourceModel,
    testingModelIdentifier,
    touchModelField,
    touchProfileField,
    touchSourceField,
    workflowResults,
  }
}
