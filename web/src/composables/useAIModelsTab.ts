import type {
  AIModelBindingItem,
  AIModelCatalogItem,
  AIModelProfileItem,
  AISourceModelItem,
} from '@/api/ai/types'
import { computed, reactive, ref, type Ref, watch } from 'vue'
import {
  getAIModelBindings,
  getAIModelProfiles,
  getAISourceModels,
} from '@/api/ai/models'
import {
  getAISourcePresets,
  getAISources,
} from '@/api/ai/sources'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'
import { useAIModelProfileState } from './aiModels/profileState'
import {
  type AIWorkflowOperationResult,
  type AIWorkflowResultStage,
  deriveAISetupWorkflow,
} from './aiModels/setupWorkflow'
import { useAISourceModelState } from './aiModels/sourceModelState'
import { useAISourceState } from './aiModels/sourceState'

export function useAIModelsTab (
  sourceCapabilityTab: Readonly<Ref<string>>,
  t: (key: string, params?: Record<string, unknown>) => string,
) {
  const noticeStore = useNoticeStore()
  const sourceModels = ref<AISourceModelItem[]>([])
  const fetchedSourceModels = ref<AIModelCatalogItem[]>([])
  const modelProfiles = ref<AIModelProfileItem[]>([])
  const modelBindings = ref<AIModelBindingItem[]>([])

  const loadingSourceModels = ref(false)
  const workflowResults = reactive<Record<AIWorkflowResultStage, AIWorkflowOperationResult | null>>({
    discovery: null,
    model: null,
    profile: null,
    provider: null,
    validation: null,
  })
  const notify = (message: string, level: 'error' | 'success' | 'warning') => {
    noticeStore.show(message, level)
  }

  function reportWorkflowResult (
    stage: AIWorkflowResultStage,
    result: AIWorkflowOperationResult,
  ) {
    workflowResults[stage] = result
  }

  function clearWorkflowResults (...stages: AIWorkflowResultStage[]) {
    const targetStages = stages.length > 0
      ? stages
      : Object.keys(workflowResults) as AIWorkflowResultStage[]
    for (const stage of targetStages) {
      workflowResults[stage] = null
    }
  }

  function startCreateSourceModel () {
    modelState.startCreateSourceModel()
  }

  function startCreateModelProfile () {
    profileState.startCreateModelProfile()
  }

  async function loadSourceModelsFor (sourceId: string) {
    if (!sourceId) {
      sourceModels.value = []
      profileState.syncActiveProfileSelection()
      modelState.startCreateSourceModel()
      return
    }
    loadingSourceModels.value = true
    try {
      const response = await getAISourceModels(sourceId)
      sourceModels.value = response.data
      profileState.syncActiveProfileSelection()
      if (!modelState.modelForm.model_id && sourceModels.value.length > 0) {
        modelState.selectSourceModel(sourceModels.value[0])
      } else if (sourceModels.value.length === 0) {
        modelState.startCreateSourceModel()
      }
    } catch (error) {
      notify(getErrorMessage(error, t('ai.modelLoadFailed')), 'error')
    } finally {
      loadingSourceModels.value = false
    }
  }

  async function loadModelsData () {
    sourceState.loadingSources.value = true
    try {
      const [presetsResponse, sourcesResponse, profilesResponse, bindingsResponse] = await Promise.all([
        getAISourcePresets(),
        getAISources(),
        getAIModelProfiles(),
        getAIModelBindings(),
      ])
      sourceState.allSourcePresets.value = presetsResponse.data
      sourceState.allSources.value = sourcesResponse.data
      modelProfiles.value = profilesResponse.data
      modelBindings.value = bindingsResponse.data
      await syncActiveCapabilitySelection()
    } catch (error) {
      notify(getErrorMessage(error, t('ai.sourceLoadFailed')), 'error')
    } finally {
      sourceState.loadingSources.value = false
    }
  }

  async function syncActiveCapabilitySelection () {
    const current = sourceState.sources.value.find(
      item => item.source_id === sourceState.sourceForm.source_id,
    )
    if (current) {
      await sourceState.selectSource(current)
      return
    }
    if (sourceState.sources.value.length > 0) {
      await sourceState.selectSource(sourceState.sources.value[0])
      return
    }
    sourceState.startCreateSource()
  }

  const sourceState = useAISourceState({
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
  })

  const modelState = useAISourceModelState({
    t,
    notify,
    sourceForm: sourceState.sourceForm,
    sourceModels,
    fetchedSourceModels,
    canFetchSourceModels: sourceState.canFetchSourceModels,
    normalizedSourceApiKeys: sourceState.normalizedSourceApiKeys,
    normalizedSourceExtraConfig: sourceState.normalizedSourceExtraConfig,
    loadSourceModelsFor,
    reportWorkflowResult,
  })

  const profileState = useAIModelProfileState({
    t,
    notify,
    currentSourceCapability: sourceState.currentSourceCapability,
    sourceModels,
    modelProfiles,
    modelBindings,
    reportWorkflowResult,
  })

  const canFetchSourceModels = computed(() => (
    sourceState.canFetchSourceModels.value
    && !modelState.fetchingSourceModels.value
  ))

  const setupWorkflow = computed(() => deriveAISetupWorkflow({
    canFetchSourceModels: canFetchSourceModels.value,
    canSaveModel: modelState.canSaveModel.value,
    canSaveProfile: profileState.canSaveProfile.value,
    canSaveSource: sourceState.canSaveSource.value,
    capability: sourceCapabilityTab.value,
    capabilityType: sourceState.currentSourceCapability.value,
    fetchedSourceModelCount: fetchedSourceModels.value.length,
    modelProfiles: modelProfiles.value,
    selectedSource: sourceState.sourceForm.source_id
      ? {
          api_base: sourceState.sourceForm.api_base,
          api_key_env_name: sourceState.sourceForm.api_key_env_name,
          api_keys: sourceState.sourceForm.api_keys,
          enabled: sourceState.sourceForm.enabled,
          name: sourceState.sourceForm.name,
          preset_type: sourceState.sourceForm.preset_type,
          source_id: sourceState.sourceForm.source_id,
        }
      : null,
    sourceCount: sourceState.sources.value.length,
    sourceModels: sourceModels.value,
  }))

  watch(() => [
    sourceCapabilityTab.value,
    sourceState.sourceForm.source_id,
  ], () => {
    clearWorkflowResults()
  })

  return {
    canFetchSourceModels,
    canSaveModel: modelState.canSaveModel,
    canSaveProfile: profileState.canSaveProfile,
    canSaveSource: sourceState.canSaveSource,
    clearWorkflowResults,
    defaultSourceModel: modelState.defaultSourceModel,
    deletingModelId: modelState.deletingModelId,
    deletingSource: sourceState.deletingSource,
    displayedModelErrors: modelState.displayedModelErrors,
    displayedProfileErrors: profileState.displayedProfileErrors,
    displayedSourceErrors: sourceState.displayedSourceErrors,
    fetchedSourceModels,
    fetchingSourceModels: modelState.fetchingSourceModels,
    importingModelIdentifier: modelState.importingModelIdentifier,
    isCreatingModel: modelState.isCreatingModel,
    isCreatingProfile: profileState.isCreatingProfile,
    isCreatingSource: sourceState.isCreatingSource,
    importSourceModelCatalogItem: modelState.importSourceModelCatalogItem,
    isChatCapability: profileState.isChatCapability,
    loadingSourceModels,
    loadModelsData,
    modelBindings,
    modelForm: modelState.modelForm,
    modelProfileCount: profileState.modelProfileCount,
    modelProfiles,
    pullSourceModels: modelState.pullSourceModels,
    profileForm: profileState.profileForm,
    profileModelOptions: profileState.profileModelOptions,
    removeSource: sourceState.removeSource,
    removeSourceModel: modelState.removeSourceModel,
    saveSource: sourceState.saveSource,
    saveModelProfile: profileState.saveModelProfile,
    saveSourceModel: modelState.saveSourceModel,
    savingModel: modelState.savingModel,
    savingProfile: profileState.savingProfile,
    savingSource: sourceState.savingSource,
    selectModelProfile: profileState.selectModelProfile,
    selectSource: sourceState.selectSource,
    selectSourceModel: modelState.selectSourceModel,
    selectedModelBindingCount: profileState.selectedModelBindingCount,
    selectedModelProfile: profileState.selectedModelProfile,
    selectedSource: sourceState.selectedSource,
    setupWorkflow,
    sourceForm: sourceState.sourceForm,
    sourceModels,
    sourcePresets: sourceState.sourcePresets,
    sources: sourceState.sources,
    startCreateSource: sourceState.startCreateSource,
    startCreateModelProfile: profileState.startCreateModelProfile,
    startCreateSourceModel: modelState.startCreateSourceModel,
    taskClassOptions: profileState.taskClassOptions,
    testSourceModel: modelState.testSourceModel,
    testingModelIdentifier: modelState.testingModelIdentifier,
    touchModelField: modelState.touchModelField,
    touchProfileField: profileState.touchProfileField,
    touchSourceField: sourceState.touchSourceField,
    fallbackProfileOptions: profileState.fallbackProfileOptions,
    filteredModelProfiles: profileState.filteredModelProfiles,
    workflowResults,
  }
}
