<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.models')"
    :title="t('ai.modelsTitle')"
  >
    <template #actions>
      <v-btn :loading="loading" variant="tonal" @click="loadData">
        {{ t('common.refresh') }}
      </v-btn>
    </template>

    <v-card class="page-panel">
      <v-card-text>
        <div class="ai-model-context">
          <div class="ai-model-context__body">
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.sourceCapabilityContext') }}
            </v-chip>
            <div class="ai-model-context__title">
              {{ activeSourceCapabilityOption.title }}
            </div>
            <div class="ai-model-context__text">
              {{ t(`ai.modelFlowStepHint.${modelFlowFocus.step}`) }}
            </div>
          </div>
          <div class="ai-model-context__next">
            <div class="ai-model-context__label">
              {{ t('ai.setupNextAction') }}
            </div>
            <div class="ai-model-context__action">
              {{ t(`ai.setupAction.${setupWorkflow.nextAction.kind}`) }}
            </div>
            <v-btn
              color="primary"
              prepend-icon="mdi-crosshairs-gps"
              variant="tonal"
              @click="handleModelPrimaryAction(setupWorkflow.nextAction.kind)"
            >
              {{ t('ai.modelFocusNextAction') }}
            </v-btn>
          </div>
        </div>

        <div
          :aria-label="t('ai.sourceCapabilitySwitcherLabel')"
          class="ai-source-capability-switcher"
          role="group"
        >
          <button
            v-for="item in sourceCapabilityOptions"
            :key="item.value"
            :aria-pressed="sourceCapabilityTab === item.value"
            class="ai-source-capability-option"
            :class="{ 'ai-source-capability-option--active': sourceCapabilityTab === item.value }"
            type="button"
            @click="sourceCapabilityTab = item.value"
          >
            <v-icon :icon="item.icon" size="18" />
            <span>{{ item.title }}</span>
          </button>
        </div>

        <div class="ai-model-workspace">
          <template v-if="!sourceCapabilityReady">
            <v-sheet class="surface-gradient-card pa-4">
              <div class="empty-state-text">{{ t('ai.sourceCapabilityComingSoon') }}</div>
              <div class="empty-state-hint mt-2">{{ t('ai.sourceCapabilityComingSoonHint') }}</div>
            </v-sheet>
          </template>

          <template v-else>
            <SplitPane class="ai-model-workbench">
              <template #sidebar>
                <AISourceListPanel
                  :active-source-id="sourceForm.source_id"
                  :empty-action-label="t('ai.setupAction.createProvider')"
                  :remove-source-item="removeSourceItem"
                  :select-source="selectSource"
                  :source-preset-label="sourcePresetLabel"
                  :sources="sources"
                  :start-create-source="startCreateSource"
                />
              </template>

              <DetailPanel
                class="ai-model-workbench__detail"
                :flat="providerDetailMode === 'empty'"
                :subtitle="providerDetailMode === 'empty' ? '' : detailPanelSubtitle"
                :title="detailPanelTitle"
              >
                <template v-if="providerDetailMode !== 'empty'" #actions />
                <template v-if="providerDetailMode !== 'empty'">
                  <AISourceWorkspace
                    v-model:source-form="sourceForm"
                    :can-save-source="canSaveSource"
                    :deleting-source="deletingSource"
                    :displayed-source-errors="displayedSourceErrors"
                    :focused="modelFlowFocus.step === 'provider' || modelFlowFocus.step === 'connection'"
                    :highlight="modelFlowFocus.highlight"
                    :is-creating-source="isCreatingSource"
                    :remove-source="removeSource"
                    :save-source="saveSource"
                    :saving-source="savingSource"
                    :select-source-protocol="selectSourceProtocol"
                    :source-preset-initial="sourcePresetInitial"
                    :source-preset-label="sourcePresetLabel"
                    :source-preset-options="sourcePresetOptions"
                    :source-presets="sourcePresets"
                    :touch-source-field="touchSourceField"
                    :workflow="setupWorkflow"
                    :workflow-result="workflowResults.provider"
                  />

                  <AISourceModelsPanel
                    v-model:model-form="modelForm"
                    v-model:profile-form="profileForm"
                    :can-fetch-source-models="canFetchSourceModels"
                    :can-save-model="canSaveModel"
                    :can-save-profile="canSaveProfile"
                    :deleting-model-id="deletingModelId"
                    :displayed-model-errors="displayedModelErrors"
                    :displayed-profile-errors="displayedProfileErrors"
                    :fallback-profile-options="fallbackProfileOptions"
                    :fetched-source-models="fetchedSourceModels"
                    :fetching-source-models="fetchingSourceModels"
                    :filtered-model-profiles="filteredModelProfiles"
                    :focused-step="modelFlowFocus.step"
                    :highlight="modelFlowFocus.highlight"
                    :import-source-model-catalog-item="importSourceModelCatalogItem"
                    :importing-model-identifier="importingModelIdentifier"
                    :is-chat-capability="isChatCapability"
                    :is-creating-model="isCreatingModel"
                    :is-creating-profile="isCreatingProfile"
                    :loading-source-models="loadingSourceModels"
                    :model-profile-count="modelProfileCount"
                    :profile-model-options="profileModelOptions"
                    :pull-source-models="pullSourceModels"
                    :remove-source-model="removeSourceModel"
                    :save-model-profile="saveModelProfile"
                    :save-source-model="saveSourceModel"
                    :saving-model="savingModel"
                    :saving-profile="savingProfile"
                    :select-model-profile="selectModelProfile"
                    :select-source-model="selectSourceModel"
                    :selected-model-binding-count="selectedModelBindingCount"
                    :source-form="sourceForm"
                    :source-models="sourceModels"
                    :start-create-model-profile="startCreateModelProfile"
                    :start-create-source-model="startCreateSourceModel"
                    :task-class-options="taskClassOptions"
                    :test-source-model="testSourceModel"
                    :testing-model-identifier="testingModelIdentifier"
                    :touch-model-field="touchModelField"
                    :touch-profile-field="touchProfileField"
                    :workflow="setupWorkflow"
                    :workflow-results="workflowResults"
                  />
                </template>
                <div v-else class="ai-provider-empty-state">
                  <v-icon icon="mdi-cursor-default-click" size="52" />
                  <div class="ai-provider-empty-state__text">
                    {{ t('ai.sourceProviderPickPrompt') }}
                  </div>
                </div>
              </DetailPanel>
            </SplitPane>
          </template>
        </div>
      </v-card-text>
    </v-card>
  </PageScaffold>
</template>

<script setup lang="ts">
  import type { AISetupNextActionKind } from '@/composables/aiModels/setupWorkflow'
  import type {
    AISetupRouteIntent,
    AISourceCapabilityRouteValue,
  } from '@/views/ai/routeState'
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import {
    DetailPanel,
    PageScaffold,
    SplitPane,
  } from '@/components/workbench'
  import { useAIModelsTab } from '@/composables/useAIModelsTab'
  import AISourceListPanel from '@/views/ai/AISourceListPanel.vue'
  import AISourceModelsPanel from '@/views/ai/AISourceModelsPanel.vue'
  import AISourceWorkspace from '@/views/ai/AISourceWorkspace.vue'
  import { resolveAIModelFlowFocus } from '@/views/ai/modelFlowState'
  import {
    useAIPageLoader,
    useAISourceCapabilityOptions,
  } from '@/views/ai/pageHelpers'
  import {
    normalizeAICapabilityRouteValue,
    normalizeAISetupRouteIntent,
    resolveAISetupActionRoute,
  } from '@/views/ai/routeState'
  import '@/views/ai/panelShared.css'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  let applyingRouteState = false

  const sourceCapabilityTab = ref<AISourceCapabilityRouteValue>('chat')
  const appliedSetupIntentKey = ref('')
  const { errorMessage, loading, runPageLoad } = useAIPageLoader(
    () => t('ai.loadFailed'),
    () => applySetupRouteIntent(),
  )
  const { sourceCapabilityOptions } = useAISourceCapabilityOptions(t)

  const {
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
    importingModelIdentifier,
    isChatCapability,
    testingModelIdentifier,
    importSourceModelCatalogItem,
    loadingSourceModels,
    isCreatingModel,
    isCreatingProfile,
    isCreatingSource,
    loadModelsData,
    modelForm,
    modelProfileCount,
    pullSourceModels,
    profileForm,
    profileModelOptions,
    providerDetailMode,
    removeSource,
    removeSourceModel,
    saveSource,
    saveModelProfile,
    saveSourceModel,
    savingModel,
    savingProfile,
    savingSource,
    selectSourceProtocol,
    selectModelProfile,
    selectSource,
    selectSourceModel,
    selectedModelBindingCount,
    sourceForm,
    sourceModels,
    setupWorkflow,
    sourcePresets,
    sources,
    startCreateSource,
    startCreateModelProfile,
    startCreateSourceModel,
    taskClassOptions,
    testSourceModel,
    touchProfileField,
    touchModelField,
    touchSourceField,
    workflowResults,
  } = useAIModelsTab(sourceCapabilityTab, t)

  const sourceCapabilityReady = computed(() => (
    sourceCapabilityTab.value === 'chat'
    || sourceCapabilityTab.value === 'embedding'
    || sourceCapabilityTab.value === 'stt'
    || sourceCapabilityTab.value === 'tts'
    || sourceCapabilityTab.value === 'rerank'
  ))
  const sourcePresetOptions = computed(() => sourcePresets.value.map(item => ({
    title: item.display_name,
    value: item.preset_type,
  })))
  const activeSourceCapabilityOption = computed(() => (
    sourceCapabilityOptions.value.find(item => item.value === sourceCapabilityTab.value)
    ?? sourceCapabilityOptions.value[0]
  ))
  const modelFlowFocus = computed(() => resolveAIModelFlowFocus({
    intent: currentSetupRouteIntent(),
    workflowDependency: setupWorkflow.value.dependency,
    workflowNextAction: setupWorkflow.value.nextAction.kind,
    workflowTargetStep: setupWorkflow.value.nextAction.targetStep,
  }))
  const detailPanelTitle = computed(() => {
    if (providerDetailMode.value === 'creating') {
      return t('ai.creatingSource')
    }
    if (providerDetailMode.value === 'selected') {
      return sourceForm.name || t('ai.sourceConfigTitle')
    }
    return ''
  })
  const detailPanelSubtitle = computed(() => {
    if (providerDetailMode.value === 'creating') {
      return t('ai.sourceCreateHint')
    }
    if (providerDetailMode.value === 'selected') {
      return sourceForm.api_base || t('ai.sourceConfigHint')
    }
    return ''
  })

  function sourcePresetLabel (value: string) {
    return sourcePresets.value.find(item => item.preset_type === value)?.display_name ?? value
  }

  function sourcePresetInitial (value: string) {
    return sourcePresetLabel(value).slice(0, 1).toUpperCase()
  }

  async function removeSourceItem (item: Parameters<typeof selectSource>[0]) {
    await selectSource(item)
    await removeSource()
  }

  async function handleModelPrimaryAction (kind: AISetupNextActionKind) {
    await router.push(resolveAISetupActionRoute(kind, sourceCapabilityTab.value))
    applySetupRouteIntent()
  }

  function currentSetupRouteIntent (): AISetupRouteIntent | '' {
    return normalizeAISetupRouteIntent(route.query.intent)
  }

  function applyRouteState () {
    const nextSourceCapabilityTab = normalizeAICapabilityRouteValue(route.query.capability)

    if (sourceCapabilityTab.value === nextSourceCapabilityTab) {
      return
    }

    applyingRouteState = true
    sourceCapabilityTab.value = nextSourceCapabilityTab
    applyingRouteState = false
  }

  function syncRouteQuery () {
    const nextQuery: Record<string, string> = {
      capability: sourceCapabilityTab.value,
    }
    if (typeof route.query.intent === 'string' && route.query.intent) {
      nextQuery.intent = route.query.intent
    }

    if (
      route.query.capability === nextQuery.capability
      && route.query.intent === nextQuery.intent
    ) {
      return
    }

    void router.replace({ query: nextQuery })
  }

  function applySetupRouteIntent () {
    const intent = currentSetupRouteIntent()
    if (!intent) {
      return
    }
    const key = `${sourceCapabilityTab.value}:${intent}`
    if (appliedSetupIntentKey.value === key) {
      return
    }
    appliedSetupIntentKey.value = key

    if (intent === 'createProvider') {
      startCreateSource()
      return
    }
    if (intent === 'createModel') {
      if (providerDetailMode.value === 'empty') {
        return
      }
      startCreateSourceModel()
      return
    }
    if (intent === 'defaultModel') {
      const item = sourceModels.value.find(model => model.enabled) ?? sourceModels.value[0]
      if (item) {
        selectSourceModel(item)
        modelForm.is_default = true
        clearWorkflowResults('model')
      }
      return
    }
    if (intent === 'createProfile' || intent === 'profile') {
      if (providerDetailMode.value === 'empty') {
        return
      }
      startCreateModelProfile()
    }
  }

  async function loadData () {
    await runPageLoad(loadModelsData)
  }

  applyRouteState()

  onMounted(() => {
    applyRouteState()
    void loadData()
  })

  watch(() => [
    route.query.capability,
    route.query.intent,
  ], () => {
    applyRouteState()
    applySetupRouteIntent()
  })

  watch(sourceCapabilityTab, () => {
    if (applyingRouteState) return
    syncRouteQuery()
  }, { flush: 'sync' })
</script>

<style scoped>
.ai-model-workspace {
  min-width: 0;
}

.ai-provider-empty-state {
  display: flex;
  min-height: 380px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: rgba(var(--v-theme-on-surface), 0.68);
  text-align: center;
}

.ai-provider-empty-state__text {
  font-size: 1rem;
  font-weight: 560;
  line-height: 1.45;
}

.ai-model-context {
  display: grid;
  min-width: 0;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
  padding: 16px;
  border: 1px solid rgba(var(--v-theme-outline-variant), 0.3);
  border-radius: var(--shape-large);
  background:
    linear-gradient(
      135deg,
      rgba(var(--v-theme-primary), 0.07),
      rgba(var(--v-theme-surface-container), 0.82) 42%,
      rgba(var(--v-theme-surface-container-high), 0.66)
    );
}

.ai-model-context__body {
  min-width: 0;
}

.ai-model-context__title {
  margin-top: 10px;
  color: rgb(var(--v-theme-on-surface));
  font-size: 1.08rem;
  font-weight: 740;
  line-height: 1.32;
}

.ai-model-context__text {
  max-width: 72ch;
  margin-top: 6px;
  color: rgba(var(--v-theme-on-surface), 0.66);
  font-size: 0.9rem;
  line-height: 1.55;
}

.ai-model-context__next {
  display: flex;
  min-width: 220px;
  flex-direction: column;
  gap: 8px;
  align-items: flex-end;
}

.ai-model-context__label {
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 0.76rem;
  font-weight: 680;
  line-height: 1.35;
}

.ai-model-context__action {
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.92rem;
  font-weight: 720;
  line-height: 1.35;
  text-align: right;
}

.ai-source-capability-switcher {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0 16px;
  padding: 8px;
  border: 1px solid rgba(var(--v-theme-outline-variant), 0.24);
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-surface-container), 0.56);
}

.ai-source-capability-option {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid transparent;
  border-radius: var(--shape-small);
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.72);
  cursor: pointer;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 660;
  line-height: 1.35;
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    color 160ms ease,
    transform 160ms ease;
}

.ai-source-capability-option:hover {
  background: rgba(var(--v-theme-primary), 0.07);
  color: rgb(var(--v-theme-on-surface));
  transform: translateY(-1px);
}

.ai-source-capability-option:active {
  transform: translateY(0);
}

.ai-source-capability-option:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.72);
  outline-offset: 2px;
}

.ai-source-capability-option--active {
  border-color: rgba(var(--v-theme-primary), 0.36);
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}

.ai-model-workbench,
.ai-model-workbench__detail {
  min-width: 0;
}

@media (max-width: 640px) {
  .ai-model-context {
    grid-template-columns: 1fr;
  }

  .ai-model-context__next {
    min-width: 0;
    align-items: stretch;
  }

  .ai-model-context__action {
    text-align: left;
  }

  .ai-source-capability-switcher {
    display: grid;
    grid-template-columns: 1fr;
  }

  .ai-source-capability-option {
    justify-content: flex-start;
    width: 100%;
  }
}

</style>
