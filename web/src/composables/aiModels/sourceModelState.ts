import type { AIModelCatalogItem, AISourceModelItem } from '@/api/ai/types'
import { computed, type ComputedRef, reactive, ref, type Ref } from 'vue'
import {
  createAISourceModel,
  deleteAISourceModel,
  fetchAISourceModels,
  testAISourceModel,
  updateAISourceModel,
} from '@/api/ai/models'
import { getErrorMessage } from '@/api/client'
import {
  buildModelSnapshot,
  type ModelFormState,
  type SourceFormState,
} from './formState'

type NoticeLevel = 'error' | 'success' | 'warning'
type ModelTouchedField = 'display_name' | 'model_identifier'

interface UseAISourceModelStateOptions {
  t: (key: string, params?: Record<string, unknown>) => string
  notify: (message: string, level: NoticeLevel) => void
  sourceForm: SourceFormState
  sourceModels: Ref<AISourceModelItem[]>
  fetchedSourceModels: Ref<AIModelCatalogItem[]>
  canFetchSourceModels: Readonly<ComputedRef<boolean>>
  normalizedSourceApiKeys: Readonly<ComputedRef<string[]>>
  normalizedSourceExtraConfig: Readonly<ComputedRef<Record<string, unknown>>>
  loadSourceModelsFor: (sourceId: string) => Promise<void>
}

export function useAISourceModelState ({
  t,
  notify,
  sourceForm,
  sourceModels,
  fetchedSourceModels,
  canFetchSourceModels,
  normalizedSourceApiKeys,
  normalizedSourceExtraConfig,
  loadSourceModelsFor,
}: UseAISourceModelStateOptions) {
  const fetchingSourceModels = ref(false)
  const savingModel = ref(false)
  const importingModelIdentifier = ref('')
  const testingModelIdentifier = ref('')
  const deletingModelId = ref('')

  const modelBaseline = ref('')
  const modelSubmitAttempted = ref(false)
  const modelTouched = reactive<Record<ModelTouchedField, boolean>>({
    model_identifier: false,
    display_name: false,
  })

  const modelForm = reactive<ModelFormState>({
    model_id: '',
    source_id: '',
    model_identifier: '',
    display_name: '',
    enabled: true,
    is_default: false,
  })

  const modelErrors = computed(() => ({
    model_identifier:
      modelForm.model_identifier.trim().length === 0
        ? t('ai.modelIdentifierRequired')
        : '',
    display_name:
      modelForm.display_name.trim().length === 0
        ? t('ai.modelDisplayNameRequired')
        : '',
  }))

  const displayedModelErrors = computed(() => ({
    model_identifier:
      modelTouched.model_identifier || modelSubmitAttempted.value
        ? modelErrors.value.model_identifier
        : '',
    display_name:
      modelTouched.display_name || modelSubmitAttempted.value
        ? modelErrors.value.display_name
        : '',
  }))

  const modelValid = computed(() => (
    !modelErrors.value.model_identifier && !modelErrors.value.display_name
  ))
  const modelDirty = computed(() => (
    buildModelSnapshot(modelForm) !== modelBaseline.value
  ))
  const isCreatingModel = computed(() => modelForm.model_id.length === 0)
  const canSaveModel = computed(() => (
    modelValid.value
    && modelDirty.value
    && sourceForm.source_id.length > 0
    && !savingModel.value
  ))
  const defaultSourceModel = computed(() => (
    sourceModels.value.find(item => item.is_default) ?? null
  ))

  function resetModelValidation () {
    modelSubmitAttempted.value = false
    modelTouched.model_identifier = false
    modelTouched.display_name = false
  }

  function syncModelBaseline () {
    modelBaseline.value = buildModelSnapshot(modelForm)
  }

  function touchModelField (field: ModelTouchedField) {
    modelTouched[field] = true
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
      notify(
        modelErrors.value.model_identifier
        || modelErrors.value.display_name
        || t('ai.modelSaveFailed'),
        'error',
      )
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
      notify(t('ai.modelSaved'), 'success')
    } catch (error) {
      notify(getErrorMessage(error, t('ai.modelSaveFailed')), 'error')
    } finally {
      savingModel.value = false
    }
  }

  async function removeSourceModel (modelId: string) {
    deletingModelId.value = modelId
    try {
      await deleteAISourceModel(modelId, sourceForm.source_id || undefined)
      await loadSourceModelsFor(sourceForm.source_id)
      notify(t('ai.modelDeleted'), 'success')
    } catch (error) {
      notify(getErrorMessage(error, t('ai.modelDeleteFailed')), 'error')
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
      notify(t('ai.modelSaved'), 'success')
    } catch (error) {
      notify(getErrorMessage(error, t('ai.modelSaveFailed')), 'error')
    } finally {
      importingModelIdentifier.value = ''
    }
  }

  async function pullSourceModels () {
    if (!canFetchSourceModels.value || fetchingSourceModels.value) {
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
      notify(
        response.data.length > 0
          ? t('ai.modelsFetched')
          : t('ai.modelFetchEmpty'),
        response.data.length > 0 ? 'success' : 'warning',
      )
    } catch (error) {
      notify(getErrorMessage(error, t('ai.modelFetchFailed')), 'error')
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
      notify(
        output
          ? t('ai.modelTestSucceededWithOutput', { output })
          : t('ai.modelTestSucceeded'),
        'success',
      )
    } catch (error) {
      notify(getErrorMessage(error, t('ai.modelTestFailed')), 'error')
    } finally {
      testingModelIdentifier.value = ''
    }
  }

  return {
    canSaveModel,
    defaultSourceModel,
    deletingModelId,
    displayedModelErrors,
    fetchingSourceModels,
    importSourceModelCatalogItem,
    importingModelIdentifier,
    isCreatingModel,
    modelForm,
    pullSourceModels,
    removeSourceModel,
    saveSourceModel,
    savingModel,
    selectSourceModel,
    startCreateSourceModel,
    testSourceModel,
    testingModelIdentifier,
    touchModelField,
  }
}
