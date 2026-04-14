import type {
  AIModelBindingItem,
  AIModelCatalogItem,
  AIModelProfileItem,
  AISourceItem,
  AISourceModelItem,
  AISourcePresetItem,
} from '@/api'
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
} from '@/api'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

interface SourceFormState {
  source_id: string
  name: string
  preset_type: string
  capability_type: string
  api_base: string
  api_keys: string[]
  api_key_env_name: string
  proxy: string
  enabled: boolean
  timeout_seconds: number | null
  embedding_dimensions: number | null
  stt_language: string
  tts_voice: string
  tts_response_format: string
  rerank_api_suffix: string
  rerank_top_n: number | null
}

interface ModelFormState {
  model_id: string
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
}

interface ProfileFormState {
  profile_id: string
  name: string
  model_id: string
  task_class: string
  priority: number
  enabled: boolean
  fallback_profile_id: string
}

function buildSourceSnapshot (form: SourceFormState) {
  return JSON.stringify({
    source_id: form.source_id,
    name: form.name.trim(),
    preset_type: form.preset_type,
    capability_type: form.capability_type,
    api_base: form.api_base.trim(),
    api_keys: normalizeApiKeys(form.api_keys),
    api_key_env_name: form.api_key_env_name.trim(),
    proxy: form.proxy.trim(),
    enabled: form.enabled,
    timeout_seconds: form.timeout_seconds,
    embedding_dimensions: form.embedding_dimensions,
    stt_language: form.stt_language.trim(),
    tts_voice: form.tts_voice.trim(),
    tts_response_format: form.tts_response_format.trim(),
    rerank_api_suffix: form.rerank_api_suffix.trim(),
    rerank_top_n: form.rerank_top_n,
  })
}

function buildModelSnapshot (form: ModelFormState) {
  return JSON.stringify({
    model_id: form.model_id,
    source_id: form.source_id,
    model_identifier: form.model_identifier.trim(),
    display_name: form.display_name.trim(),
    enabled: form.enabled,
    is_default: form.is_default,
  })
}

function buildProfileSnapshot (form: ProfileFormState) {
  return JSON.stringify({
    profile_id: form.profile_id,
    name: form.name.trim(),
    model_id: form.model_id,
    task_class: form.task_class,
    priority: form.priority,
    enabled: form.enabled,
    fallback_profile_id: form.fallback_profile_id,
  })
}

export function useAIModelsTab (
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
  const fetchingSourceModels = ref(false)
  const savingSource = ref(false)
  const savingModel = ref(false)
  const savingProfile = ref(false)
  const importingModelIdentifier = ref('')
  const testingModelIdentifier = ref('')
  const deletingSource = ref(false)
  const deletingModelId = ref('')

  const sourceBaseline = ref('')
  const sourceSubmitAttempted = ref(false)
  const sourceTouched = reactive({
    name: false,
    preset_type: false,
  })

  const modelBaseline = ref('')
  const modelSubmitAttempted = ref(false)
  const modelTouched = reactive({
    model_identifier: false,
    display_name: false,
  })
  const profileBaseline = ref('')
  const profileSubmitAttempted = ref(false)
  const profileTouched = reactive({
    name: false,
    model_id: false,
  })

  const sourceForm = reactive<SourceFormState>({
    source_id: '',
    name: '',
    preset_type: '',
    capability_type: resolveSourceCapabilityType(sourceCapabilityTab.value),
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
  })

  const modelForm = reactive<ModelFormState>({
    model_id: '',
    source_id: '',
    model_identifier: '',
    display_name: '',
    enabled: true,
    is_default: false,
  })
  const profileForm = reactive<ProfileFormState>({
    profile_id: '',
    name: '',
    model_id: '',
    task_class: 'reply_default',
    priority: 100,
    enabled: true,
    fallback_profile_id: '',
  })

  const currentSourceCapability = computed(() => resolveSourceCapabilityType(sourceCapabilityTab.value))
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
    sourcePresets.value.find(item => item.preset_type === sourceForm.preset_type) ?? null
  ))
  const isChatCapability = computed(() => currentSourceCapability.value === 'chat_completion')
  const configuredSourceModelIds = computed(() => new Set(sourceModels.value.map(item => item.model_id)))
  const filteredModelProfiles = computed(() => modelProfiles.value.filter(
    item => configuredSourceModelIds.value.has(item.model_id),
  ))
  const modelProfileCount = computed(() => filteredModelProfiles.value.length)
  const selectedModelProfile = computed(() => (
    filteredModelProfiles.value.find(item => item.profile_id === profileForm.profile_id) ?? null
  ))
  const selectedModelBindingCount = computed(() => modelBindings.value.length)

  const sourceErrors = computed(() => ({
    name: sourceForm.name.trim().length === 0 ? t('ai.sourceNameRequired') : '',
    preset_type: sourceForm.preset_type.trim().length === 0 ? t('ai.sourcePresetRequired') : '',
  }))

  const displayedSourceErrors = computed(() => ({
    name: sourceTouched.name || sourceSubmitAttempted.value ? sourceErrors.value.name : '',
    preset_type: sourceTouched.preset_type || sourceSubmitAttempted.value ? sourceErrors.value.preset_type : '',
  }))

  const sourceValid = computed(() => !sourceErrors.value.name && !sourceErrors.value.preset_type)
  const sourceDirty = computed(() => buildSourceSnapshot(sourceForm) !== sourceBaseline.value)
  const isCreatingSource = computed(() => sourceForm.source_id.length === 0)
  const canSaveSource = computed(() => sourceValid.value && sourceDirty.value && !savingSource.value)

  const modelErrors = computed(() => ({
    model_identifier: modelForm.model_identifier.trim().length === 0 ? t('ai.modelIdentifierRequired') : '',
    display_name: modelForm.display_name.trim().length === 0 ? t('ai.modelDisplayNameRequired') : '',
  }))

  const displayedModelErrors = computed(() => ({
    model_identifier: modelTouched.model_identifier || modelSubmitAttempted.value ? modelErrors.value.model_identifier : '',
    display_name: modelTouched.display_name || modelSubmitAttempted.value ? modelErrors.value.display_name : '',
  }))

  const modelValid = computed(() => !modelErrors.value.model_identifier && !modelErrors.value.display_name)
  const modelDirty = computed(() => buildModelSnapshot(modelForm) !== modelBaseline.value)
  const isCreatingModel = computed(() => modelForm.model_id.length === 0)
  const canSaveModel = computed(() => (
    modelValid.value
    && modelDirty.value
    && sourceForm.source_id.length > 0
    && !savingModel.value
  ))
  const profileErrors = computed(() => ({
    name: profileForm.name.trim().length === 0 ? t('ai.modelProfileNameRequired') : '',
    model_id: profileForm.model_id.trim().length === 0 ? t('ai.modelProfileModelRequired') : '',
  }))
  const displayedProfileErrors = computed(() => ({
    name: profileTouched.name || profileSubmitAttempted.value ? profileErrors.value.name : '',
    model_id: profileTouched.model_id || profileSubmitAttempted.value ? profileErrors.value.model_id : '',
  }))
  const profileValid = computed(() => !profileErrors.value.name && !profileErrors.value.model_id)
  const profileDirty = computed(() => buildProfileSnapshot(profileForm) !== profileBaseline.value)
  const isCreatingProfile = computed(() => profileForm.profile_id.length === 0)
  const canSaveProfile = computed(() => (
    isChatCapability.value
    && profileValid.value
    && profileDirty.value
    && !savingProfile.value
  ))
  const taskClassOptions = computed(() => [
    { title: t('ai.modelTaskClassReplyDefault'), value: 'reply_default' },
    { title: t('ai.modelTaskClassReplyRoleplay'), value: 'reply_roleplay' },
    { title: t('ai.modelTaskClassToolOrchestration'), value: 'tool_orchestration' },
    { title: t('ai.modelTaskClassMemoryExtraction'), value: 'memory_extraction' },
    { title: t('ai.modelTaskClassPlannerLight'), value: 'planner_light' },
    { title: t('ai.modelTaskClassReasoningHeavy'), value: 'reasoning_heavy' },
  ])
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

  const canFetchSourceModels = computed(() => (
    sourceForm.preset_type.trim().length > 0
    && sourceForm.api_base.trim().length > 0
    && (
      normalizeApiKeys(sourceForm.api_keys).length > 0
      || sourceForm.api_key_env_name.trim().length > 0
    )
    && !fetchingSourceModels.value
  ))

  const normalizedSourceApiKeys = computed(() => normalizeApiKeys(sourceForm.api_keys))
  const normalizedSourceExtraConfig = computed(() => buildSourceExtraConfig(sourceForm))
  const defaultSourceModel = computed(() => sourceModels.value.find(item => item.is_default) ?? null)

  watch(selectedSourcePreset, preset => {
    if (!preset) {
      return
    }
    sourceForm.capability_type = preset.capability_type
    if (!sourceForm.api_base.trim() && preset.default_api_base) {
      sourceForm.api_base = preset.default_api_base
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

  function resetModelValidation () {
    modelSubmitAttempted.value = false
    modelTouched.model_identifier = false
    modelTouched.display_name = false
  }

  function resetProfileValidation () {
    profileSubmitAttempted.value = false
    profileTouched.name = false
    profileTouched.model_id = false
  }

  function syncSourceBaseline () {
    sourceBaseline.value = buildSourceSnapshot(sourceForm)
  }

  function syncModelBaseline () {
    modelBaseline.value = buildModelSnapshot(modelForm)
  }

  function syncProfileBaseline () {
    profileBaseline.value = buildProfileSnapshot(profileForm)
  }

  function touchSourceField (field: keyof typeof sourceTouched) {
    sourceTouched[field] = true
  }

  function touchModelField (field: keyof typeof modelTouched) {
    modelTouched[field] = true
  }

  function touchProfileField (field: keyof typeof profileTouched) {
    profileTouched[field] = true
  }

  function selectModelProfile (item: AIModelProfileItem) {
    profileForm.profile_id = item.profile_id
    profileForm.name = item.name
    profileForm.model_id = item.model_id
    profileForm.task_class = item.task_class
    profileForm.priority = item.priority
    profileForm.enabled = item.enabled
    profileForm.fallback_profile_id = item.fallback_profile_id ?? ''
    syncProfileBaseline()
    resetProfileValidation()
  }

  function startCreateModelProfile () {
    profileForm.profile_id = ''
    profileForm.name = ''
    profileForm.model_id = sourceModels.value[0]?.model_id ?? ''
    profileForm.task_class = 'reply_default'
    profileForm.priority = 100
    profileForm.enabled = true
    profileForm.fallback_profile_id = ''
    syncProfileBaseline()
    resetProfileValidation()
  }

  function syncActiveProfileSelection () {
    if (!isChatCapability.value) {
      startCreateModelProfile()
      return
    }
    const current = filteredModelProfiles.value.find(item => item.profile_id === profileForm.profile_id)
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

  async function loadSourceModelsFor (sourceId: string) {
    if (!sourceId) {
      sourceModels.value = []
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
      noticeStore.show(getErrorMessage(error, t('ai.modelLoadFailed')), 'error')
    } finally {
      loadingSourceModels.value = false
    }
  }

  async function loadModelsData () {
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
      noticeStore.show(getErrorMessage(error, t('ai.sourceLoadFailed')), 'error')
    } finally {
      loadingSources.value = false
    }
  }

  async function selectSource (item: AISourceItem) {
    sourceForm.source_id = item.source_id
    sourceForm.name = item.name
    sourceForm.preset_type = item.preset_type
    sourceForm.capability_type = item.capability_type
    sourceForm.api_base = item.api_base ?? ''
    sourceForm.api_keys = extractSourceApiKeys(item)
    sourceForm.api_key_env_name = item.api_key_env_name ?? ''
    sourceForm.proxy = extractOptionalString(item.extra_config?.proxy)
    sourceForm.enabled = item.enabled
    sourceForm.timeout_seconds = item.timeout_seconds
    sourceForm.embedding_dimensions = extractOptionalInt(item.extra_config?.embedding_dimensions)
    sourceForm.stt_language = extractOptionalString(item.extra_config?.stt_language)
    sourceForm.tts_voice = extractOptionalString(item.extra_config?.tts_voice) || 'alloy'
    sourceForm.tts_response_format = extractOptionalString(item.extra_config?.tts_response_format) || 'wav'
    sourceForm.rerank_api_suffix = extractOptionalString(item.extra_config?.rerank_api_suffix) || '/rerank'
    sourceForm.rerank_top_n = extractOptionalInt(item.extra_config?.rerank_top_n) ?? 2
    syncSourceBaseline()
    resetSourceValidation()
    fetchedSourceModels.value = []
    await loadSourceModelsFor(item.source_id)
  }

  function startCreateSource () {
    const defaultPreset = sourcePresets.value[0]
    sourceForm.source_id = ''
    sourceForm.name = ''
    sourceForm.preset_type = defaultPreset?.preset_type ?? defaultPresetTypeFor(sourceCapabilityTab.value)
    sourceForm.capability_type = currentSourceCapability.value
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
      noticeStore.show(sourceErrors.value.name || sourceErrors.value.preset_type || t('ai.sourceSaveFailed'), 'error')
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
      }
      const response = sourceForm.source_id
        ? await updateAISource({ ...payload, source_id: sourceForm.source_id })
        : await createAISource(payload)
      if (response.data) {
        await loadModelsData()
        await selectSource(response.data)
      }
      noticeStore.show(t('ai.sourceSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.sourceSaveFailed')), 'error')
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
      noticeStore.show(t('ai.sourceDeleted'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.sourceDeleteFailed')), 'error')
    } finally {
      deletingSource.value = false
    }
  }

  function selectSourceModel (item: AISourceModelItem) {
    modelForm.model_id = item.model_id
    modelForm.source_id = item.source_id
    modelForm.model_identifier = item.model_identifier
    modelForm.display_name = item.display_name
    modelForm.enabled = item.enabled
    modelForm.is_default = item.is_default
    syncModelBaseline()
    resetModelValidation()
  }

  function startCreateSourceModel () {
    modelForm.model_id = ''
    modelForm.source_id = sourceForm.source_id
    modelForm.model_identifier = ''
    modelForm.display_name = ''
    modelForm.enabled = true
    modelForm.is_default = sourceModels.value.length === 0
    syncModelBaseline()
    resetModelValidation()
  }

  async function saveSourceModel () {
    modelSubmitAttempted.value = true
    if (!modelValid.value) {
      noticeStore.show(modelErrors.value.model_identifier || modelErrors.value.display_name || t('ai.modelSaveFailed'), 'error')
      return
    }
    if (!modelDirty.value) {
      return
    }
    savingModel.value = true
    try {
      const payload = {
        model_id: modelForm.model_id || undefined,
        source_id: sourceForm.source_id,
        model_identifier: modelForm.model_identifier.trim(),
        display_name: modelForm.display_name.trim(),
        enabled: modelForm.enabled,
        is_default: modelForm.is_default,
        extra_params: {},
      }
      const response = modelForm.model_id
        ? await updateAISourceModel({ ...payload, model_id: modelForm.model_id })
        : await createAISourceModel(payload)
      if (response.data) {
        await loadSourceModelsFor(sourceForm.source_id)
        selectSourceModel(response.data)
      }
      noticeStore.show(t('ai.modelSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.modelSaveFailed')), 'error')
    } finally {
      savingModel.value = false
    }
  }

  async function removeSourceModel (modelId: string) {
    deletingModelId.value = modelId
    try {
      await deleteAISourceModel(modelId, sourceForm.source_id || undefined)
      await loadSourceModelsFor(sourceForm.source_id)
      noticeStore.show(t('ai.modelDeleted'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.modelDeleteFailed')), 'error')
    } finally {
      deletingModelId.value = ''
    }
  }

  async function importSourceModelCatalogItem (item: AIModelCatalogItem) {
    if (!sourceForm.source_id || importingModelIdentifier.value) {
      return
    }
    importingModelIdentifier.value = item.id
    try {
      const response = await createAISourceModel({
        source_id: sourceForm.source_id,
        model_identifier: item.id,
        display_name: item.name,
        enabled: true,
        is_default: sourceModels.value.length === 0,
        extra_params: {},
      })
      if (response.data) {
        await loadSourceModelsFor(sourceForm.source_id)
        fetchedSourceModels.value = fetchedSourceModels.value.filter(
          current => current.id !== item.id,
        )
      }
      noticeStore.show(t('ai.modelSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.modelSaveFailed')), 'error')
    } finally {
      importingModelIdentifier.value = ''
    }
  }

  async function pullSourceModels () {
    if (!canFetchSourceModels.value) {
      return
    }
    fetchingSourceModels.value = true
    try {
      const response = await fetchAISourceModels({
        source_id: sourceForm.source_id || null,
        preset_type: sourceForm.preset_type,
        api_base: sourceForm.api_base.trim(),
        api_key: normalizedSourceApiKeys.value[0] || null,
        api_key_env_name: sourceForm.api_key_env_name.trim() || null,
        extra_config: normalizedSourceExtraConfig.value,
      })
      fetchedSourceModels.value = response.data
      noticeStore.show(
        response.data.length > 0 ? t('ai.modelsFetched') : t('ai.modelFetchEmpty'),
        response.data.length > 0 ? 'success' : 'warning',
      )
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.modelFetchFailed')), 'error')
    } finally {
      fetchingSourceModels.value = false
    }
  }

  async function testSourceModel (modelIdentifier: string) {
    const resolvedModelIdentifier = modelIdentifier.trim()
    if (!resolvedModelIdentifier || testingModelIdentifier.value) {
      return
    }
    testingModelIdentifier.value = resolvedModelIdentifier
    try {
      const response = await testAISourceModel({
        source_id: sourceForm.source_id || null,
        preset_type: sourceForm.preset_type,
        api_base: sourceForm.api_base.trim(),
        api_key: normalizedSourceApiKeys.value[0] || null,
        api_key_env_name: sourceForm.api_key_env_name.trim() || null,
        extra_config: normalizedSourceExtraConfig.value,
        model_identifier: resolvedModelIdentifier,
      })
      const output = response.data.content.trim()
      noticeStore.show(
        output
          ? t('ai.modelTestSucceededWithOutput', { output })
          : t('ai.modelTestSucceeded'),
        'success',
      )
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.modelTestFailed')), 'error')
    } finally {
      testingModelIdentifier.value = ''
    }
  }

  async function saveModelProfile () {
    profileSubmitAttempted.value = true
    if (!profileValid.value) {
      noticeStore.show(profileErrors.value.name || profileErrors.value.model_id || t('ai.modelProfileSaveFailed'), 'error')
      return
    }
    if (!profileDirty.value) {
      return
    }
    savingProfile.value = true
    try {
      const response = await upsertAIModelProfile({
        profile_id: profileForm.profile_id || null,
        name: profileForm.name.trim(),
        model_id: profileForm.model_id,
        task_class: profileForm.task_class,
        priority: profileForm.priority,
        enabled: profileForm.enabled,
        fallback_profile_id: profileForm.fallback_profile_id || null,
      })
      if (response.data) {
        const profilesResponse = await getAIModelProfiles()
        modelProfiles.value = profilesResponse.data
        selectModelProfile(response.data)
      }
      noticeStore.show(t('ai.modelProfileSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.modelProfileSaveFailed')), 'error')
    } finally {
      savingProfile.value = false
    }
  }

  async function syncActiveCapabilitySelection () {
    const current = sources.value.find(item => item.source_id === sourceForm.source_id)
    if (current) {
      await selectSource(current)
      return
    }
    if (sources.value.length > 0) {
      await selectSource(sources.value[0])
      return
    }
    startCreateSource()
    sourceModels.value = []
  }

  return {
    canFetchSourceModels,
    canSaveModel,
    canSaveProfile,
    canSaveSource,
    defaultSourceModel,
    deletingModelId,
    deletingSource,
    displayedModelErrors,
    displayedProfileErrors,
    displayedSourceErrors,
    fetchedSourceModels,
    fetchingSourceModels,
    importingModelIdentifier,
    isCreatingModel,
    isCreatingProfile,
    isCreatingSource,
    importSourceModelCatalogItem,
    isChatCapability,
    loadingSourceModels,
    loadModelsData,
    modelBindings,
    modelForm,
    modelProfileCount,
    modelProfiles,
    pullSourceModels,
    profileForm,
    profileModelOptions,
    removeSource,
    removeSourceModel,
    saveSource,
    saveModelProfile,
    saveSourceModel,
    savingModel,
    savingProfile,
    savingSource,
    selectModelProfile,
    selectSource,
    selectSourceModel,
    selectedModelBindingCount,
    selectedModelProfile,
    selectedSource,
    sourceForm,
    sourceModels,
    sourcePresets,
    sources,
    startCreateSource,
    startCreateModelProfile,
    startCreateSourceModel,
    taskClassOptions,
    testSourceModel,
    testingModelIdentifier,
    touchModelField,
    touchProfileField,
    touchSourceField,
    fallbackProfileOptions,
    filteredModelProfiles,
  }
}

function resolveSourceCapabilityType (tab: string) {
  if (tab === 'embedding') {
    return 'embedding'
  }
  if (tab === 'stt') {
    return 'speech_to_text'
  }
  if (tab === 'tts') {
    return 'text_to_speech'
  }
  if (tab === 'rerank') {
    return 'rerank'
  }
  return 'chat_completion'
}

function defaultPresetTypeFor (tab: string) {
  if (tab === 'embedding') {
    return 'openai_compatible_embedding'
  }
  if (tab === 'stt') {
    return 'openai_compatible_stt'
  }
  if (tab === 'tts') {
    return 'openai_compatible_tts'
  }
  if (tab === 'rerank') {
    return 'generic_rerank_api'
  }
  return 'openai_compatible'
}

function normalizeApiKeys (values: string[]) {
  return values
    .map(value => value.trim())
    .filter(Boolean)
}

function buildSourceExtraConfig (form: SourceFormState) {
  const extraConfig: Record<string, unknown> = {
    api_keys: normalizeApiKeys(form.api_keys),
  }
  if (form.capability_type === 'embedding' && form.embedding_dimensions) {
    extraConfig.embedding_dimensions = form.embedding_dimensions
  }
  if (form.proxy.trim()) {
    extraConfig.proxy = form.proxy.trim()
  }
  if (form.capability_type === 'speech_to_text' && form.stt_language.trim()) {
    extraConfig.stt_language = form.stt_language.trim()
  }
  if (form.capability_type === 'text_to_speech') {
    if (form.tts_voice.trim()) {
      extraConfig.tts_voice = form.tts_voice.trim()
    }
    if (form.tts_response_format.trim()) {
      extraConfig.tts_response_format = form.tts_response_format.trim()
    }
  }
  if (form.capability_type === 'rerank') {
    if (form.rerank_api_suffix.trim()) {
      extraConfig.rerank_api_suffix = form.rerank_api_suffix.trim()
    }
    if (typeof form.rerank_top_n === 'number' && form.rerank_top_n > 0) {
      extraConfig.rerank_top_n = form.rerank_top_n
    }
  }
  return extraConfig
}

function extractOptionalString (value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

function extractOptionalInt (value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number.parseInt(value.trim(), 10)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
}

function extractSourceApiKeys (item: AISourceItem) {
  const raw = item.extra_config?.api_keys
  if (!Array.isArray(raw)) {
    return []
  }
  return raw
    .filter((value): value is string => typeof value === 'string')
    .map(value => value.trim())
    .filter(Boolean)
}
