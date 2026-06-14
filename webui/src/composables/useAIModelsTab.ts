import type {
  AIModelProfileItem,
  AISourceModelItem,
} from '@/api/ai'
import { computed, reactive, type Ref, watch } from 'vue'
import {
  getAIModelBindings,
  getAIModelProfiles,
  getAIModelRouteBindings,
  getAIModelRouteMembers,
  getAIModelRoutes,
  getAISourcePresets,
  getAISources,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'
import {
  deriveAISetupWorkflow,
  type AIWorkflowOperationResult,
  type AIWorkflowResultStage,
} from '@/utils/aiSetupWorkflow'
import type { NoticeLevel } from '@/composables/ai-models/helpers'
import {
  useAIModelSources,
  type SourceCrossHooks,
} from '@/composables/ai-models/useAIModelSources'
import { useAIModelProfiles } from '@/composables/ai-models/useAIModelProfiles'
import { useAIModelRoutes } from '@/composables/ai-models/useAIModelRoutes'

export type AIProviderDetailMode = 'creating' | 'empty' | 'selected'

export function useAIModelsTab(
  sourceCapabilityTab: Readonly<Ref<string>>,
  t: (key: string, params?: Record<string, unknown>) => string,
) {
  const noticeStore = useNoticeStore()

  const workflowResults = reactive<Record<AIWorkflowResultStage, AIWorkflowOperationResult | null>>({
    discovery: null,
    model: null,
    profile: null,
    provider: null,
    validation: null,
  })

  function notify(message: string, level: NoticeLevel) {
    noticeStore.show(message, level)
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

  const sources = useAIModelSources(sourceCapabilityTab, t, notify, reportWorkflowResult)
  const profiles = useAIModelProfiles(
    t,
    notify,
    reportWorkflowResult,
    sources.configuredSourceModelIds,
    sources.sourceModels,
    sources.isChatCapability,
  )
  const routes = useAIModelRoutes(
    t,
    notify,
    sources.isChatCapability,
    profiles.filteredModelProfiles,
  )

  async function loadModelsData() {
    sources.loadingSources.value = true
    try {
      const [
        presetsResponse,
        sourcesResponse,
        profilesResponse,
        bindingsResponse,
        routesResponse,
        routeMembersResponse,
        routeBindingsResponse,
      ] = await Promise.all([
        getAISourcePresets(),
        getAISources(),
        getAIModelProfiles(),
        getAIModelBindings(),
        getAIModelRoutes(),
        getAIModelRouteMembers(),
        getAIModelRouteBindings(),
      ])
      sources.allSourcePresets.value = presetsResponse.data
      sources.allSources.value = sourcesResponse.data
      profiles.modelProfiles.value = profilesResponse.data
      profiles.modelBindings.value = bindingsResponse.data
      routes.modelRoutes.value = routesResponse.data
      routes.modelRouteMembers.value = routeMembersResponse.data
      routes.modelRouteBindings.value = routeBindingsResponse.data
      await sources.syncActiveCapabilitySelection()
      routes.syncActiveRouteSelection()
    } catch (error) {
      notify(getErrorMessage(error, t('ai.sourceLoadFailed')), 'error')
      throw error
    } finally {
      sources.loadingSources.value = false
    }
  }

  const sourceCrossHooks: SourceCrossHooks = {
    startCreateModelProfile: profiles.startCreateModelProfile,
    syncActiveProfileSelection: profiles.syncActiveProfileSelection,
    loadModelsData,
  }
  sources.setCrossHooks(sourceCrossHooks)

  profiles.setRouteHooks({
    syncActiveRouteSelection: routes.syncActiveRouteSelection,
  })

  const setupWorkflow = computed(() => deriveAISetupWorkflow({
    canFetchSourceModels: sources.canFetchSourceModels.value,
    canSaveModel: sources.canSaveModel.value,
    canSaveProfile: profiles.canSaveProfile.value,
    canSaveSource: sources.canSaveSource.value,
    capabilityType: sources.currentSourceCapability.value,
    fetchedSourceModelCount: sources.fetchedSourceModels.value.length,
    modelProfiles: profiles.modelProfiles.value as AIModelProfileItem[],
    selectedSource: sources.sourceForm.source_id
      ? {
          api_base: sources.sourceForm.api_base,
          api_key_configured: sources.sourceHasApiKey.value,
          api_keys: sources.normalizedSourceApiKeys.value,
          enabled: sources.sourceForm.enabled,
          name: sources.sourceForm.name,
          preset_type: sources.sourceForm.preset_type,
          source_id: sources.sourceForm.source_id,
        }
      : null,
    sourceCount: sources.sources.value.length,
    sourceModels: sources.sourceModels.value as AISourceModelItem[],
  }))

  watch(() => [
    sourceCapabilityTab.value,
    sources.sourceForm.source_id,
  ], () => {
    clearWorkflowResults()
  })

  return {
    addRouteMember: routes.addRouteMember,
    canFetchSourceModels: sources.canFetchSourceModels,
    canSaveModel: sources.canSaveModel,
    canSaveProfile: profiles.canSaveProfile,
    canSaveRoute: routes.canSaveRoute,
    canSaveSource: sources.canSaveSource,
    clearWorkflowResults,
    deletingModelId: sources.deletingModelId,
    deletingRouteId: routes.deletingRouteId,
    deletingSource: sources.deletingSource,
    displayedModelErrors: sources.displayedModelErrors,
    displayedProfileErrors: profiles.displayedProfileErrors,
    displayedRouteErrors: routes.displayedRouteErrors,
    displayedSourceErrors: sources.displayedSourceErrors,
    fetchedSourceModels: sources.fetchedSourceModels,
    fetchingSourceModels: sources.fetchingSourceModels,
    filteredModelProfiles: profiles.filteredModelProfiles,
    filteredModelRoutes: routes.filteredModelRoutes,
    importSourceModelCatalogItem: sources.importSourceModelCatalogItem,
    importingModelIdentifier: sources.importingModelIdentifier,
    isChatCapability: sources.isChatCapability,
    isCreatingModel: sources.isCreatingModel,
    isCreatingProfile: profiles.isCreatingProfile,
    isCreatingRoute: routes.isCreatingRoute,
    isCreatingSource: sources.isCreatingSource,
    loadModelsData,
    loadingSourceModels: sources.loadingSourceModels,
    loadingSources: sources.loadingSources,
    modelBindings: profiles.modelBindings,
    modelForm: sources.modelForm,
    modelProfileCount: profiles.modelProfileCount,
    modelProfiles: profiles.modelProfiles,
    modelRouteCount: routes.modelRouteCount,
    modelRouteMembers: routes.modelRouteMembers,
    modelRoutes: routes.modelRoutes,
    moveRouteMember: routes.moveRouteMember,
    profileForm: profiles.profileForm,
    profileModelOptions: profiles.profileModelOptions,
    providerDetailMode: sources.providerDetailMode,
    pullSourceModels: sources.pullSourceModels,
    removeModelRoute: routes.removeModelRoute,
    removeRouteMember: routes.removeRouteMember,
    removeSource: sources.removeSource,
    removeSourceModel: sources.removeSourceModel,
    saveModelProfile: profiles.saveModelProfile,
    saveModelRoute: routes.saveModelRoute,
    saveSource: sources.saveSource,
    saveSourceModel: sources.saveSourceModel,
    savingModel: sources.savingModel,
    savingProfile: profiles.savingProfile,
    savingRoute: routes.savingRoute,
    savingSource: sources.savingSource,
    selectModelProfile: profiles.selectModelProfile,
    selectModelRoute: routes.selectModelRoute,
    selectSource: sources.selectSource,
    selectSourceModel: sources.selectSourceModel,
    selectSourceProtocol: sources.selectSourceProtocol,
    selectedModelBindingCount: profiles.selectedModelBindingCount,
    selectedRouteBindingCount: routes.selectedRouteBindingCount,
    selectedRouteMembers: routes.selectedRouteMembers,
    selectedSource: sources.selectedSource,
    setupWorkflow,
    sourceForm: sources.sourceForm,
    sourceModels: sources.sourceModels,
    sourcePresets: sources.sourcePresets,
    sources: sources.sources,
    startCreateModelProfile: profiles.startCreateModelProfile,
    startCreateModelRoute: routes.startCreateModelRoute,
    startCreateSource: sources.startCreateSource,
    startCreateSourceModel: sources.startCreateSourceModel,
    setRouteMode: routes.setRouteMode,
    routeForm: routes.routeForm,
    routeProfileOptions: routes.routeProfileOptions,
    taskClassOptions: routes.taskClassOptions,
    testSourceModel: sources.testSourceModel,
    testingModelIdentifier: sources.testingModelIdentifier,
    touchModelField: sources.touchModelField,
    touchProfileField: profiles.touchProfileField,
    touchRouteField: routes.touchRouteField,
    touchSourceField: sources.touchSourceField,
    workflowResults,
  }
}
