import type {
  AIChatModelItem,
  AIModelCatalogItem,
  AISourceItem,
  AISourcePresetItem,
} from '@/api'
import { computed, reactive, ref, watch } from 'vue'
import {
  createAIChatModel,
  createAISource,
  deleteAIChatModel,
  deleteAISource,
  fetchAISourceModels,
  getAISourceModels,
  getAISourcePresets,
  getAISources,
  testAISourceModel,
  updateAIChatModel,
  updateAISource,
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
  enabled: boolean
  timeout_seconds: number | null
}

interface ModelFormState {
  model_id: string
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
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
    enabled: form.enabled,
    timeout_seconds: form.timeout_seconds,
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

export function useAIModelsTab (
  t: (key: string, params?: Record<string, unknown>) => string,
) {
  const noticeStore = useNoticeStore()

  const sourcePresets = ref<AISourcePresetItem[]>([])
  const sources = ref<AISourceItem[]>([])
  const sourceModels = ref<AIChatModelItem[]>([])
  const fetchedSourceModels = ref<AIModelCatalogItem[]>([])

  const loadingSources = ref(false)
  const loadingSourceModels = ref(false)
  const fetchingSourceModels = ref(false)
  const savingSource = ref(false)
  const savingModel = ref(false)
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

  const sourceForm = reactive<SourceFormState>({
    source_id: '',
    name: '',
    preset_type: 'openai_compatible',
    capability_type: 'chat_completion',
    api_base: '',
    api_keys: [],
    api_key_env_name: '',
    enabled: true,
    timeout_seconds: 120,
  })

  const modelForm = reactive<ModelFormState>({
    model_id: '',
    source_id: '',
    model_identifier: '',
    display_name: '',
    enabled: true,
    is_default: false,
  })

  const selectedSource = computed(() => (
    sources.value.find(item => item.source_id === sourceForm.source_id) ?? null
  ))

  const selectedSourcePreset = computed(() => (
    sourcePresets.value.find(item => item.preset_type === sourceForm.preset_type) ?? null
  ))

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

  function syncSourceBaseline () {
    sourceBaseline.value = buildSourceSnapshot(sourceForm)
  }

  function syncModelBaseline () {
    modelBaseline.value = buildModelSnapshot(modelForm)
  }

  function touchSourceField (field: keyof typeof sourceTouched) {
    sourceTouched[field] = true
  }

  function touchModelField (field: keyof typeof modelTouched) {
    modelTouched[field] = true
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
      const [presetsResponse, sourcesResponse] = await Promise.all([
        getAISourcePresets(),
        getAISources(),
      ])
      sourcePresets.value = presetsResponse.data
      sources.value = sourcesResponse.data
      if (!sourceForm.source_id && sources.value.length > 0) {
        await selectSource(sources.value[0])
      } else if (sources.value.length === 0) {
        startCreateSource()
        sourceModels.value = []
      }
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
    sourceForm.enabled = item.enabled
    sourceForm.timeout_seconds = item.timeout_seconds
    syncSourceBaseline()
    resetSourceValidation()
    fetchedSourceModels.value = []
    await loadSourceModelsFor(item.source_id)
  }

  function startCreateSource () {
    sourceForm.source_id = ''
    sourceForm.name = ''
    sourceForm.preset_type = sourcePresets.value[0]?.preset_type ?? 'openai_compatible'
    sourceForm.capability_type = sourcePresets.value[0]?.capability_type ?? 'chat_completion'
    sourceForm.api_base = sourcePresets.value[0]?.default_api_base ?? ''
    sourceForm.api_keys = []
    sourceForm.api_key_env_name = ''
    sourceForm.enabled = true
    sourceForm.timeout_seconds = 120
    syncSourceBaseline()
    resetSourceValidation()
    sourceModels.value = []
    fetchedSourceModels.value = []
    startCreateSourceModel()
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
        extra_config: {
          api_keys: normalizedSourceApiKeys.value,
        },
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

  function selectSourceModel (item: AIChatModelItem) {
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
        ? await updateAIChatModel({ ...payload, model_id: modelForm.model_id })
        : await createAIChatModel(payload)
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
      await deleteAIChatModel(modelId)
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
      const response = await createAIChatModel({
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

  return {
    canSaveModel,
    canSaveSource,
    canFetchSourceModels,
    defaultSourceModel,
    deletingModelId,
    deletingSource,
    displayedModelErrors,
    displayedSourceErrors,
    fetchedSourceModels,
    fetchingSourceModels,
    importingModelIdentifier,
    isCreatingModel,
    isCreatingSource,
    importSourceModelCatalogItem,
    loadingSourceModels,
    loadModelsData,
    modelForm,
    pullSourceModels,
    removeSource,
    removeSourceModel,
    saveSource,
    saveSourceModel,
    savingModel,
    savingSource,
    selectSource,
    selectSourceModel,
    selectedSource,
    sourceForm,
    sourceModels,
    sourcePresets,
    sources,
    startCreateSource,
    startCreateSourceModel,
    testSourceModel,
    testingModelIdentifier,
    touchModelField,
    touchSourceField,
  }
}

function normalizeApiKeys (values: string[]) {
  return values
    .map(value => value.trim())
    .filter(Boolean)
}

function extractSourceApiKeys (item: AISourceItem) {
  const raw = item.extra_config?.api_keys
  if (!Array.isArray(raw)) {
    return []
  }
  return raw.filter((value): value is string => typeof value === 'string').map(value => value.trim()).filter(Boolean)
}
