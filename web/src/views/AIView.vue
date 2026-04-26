<template>
  <div class="page-view">
    <div class="page-header">
      <h1 class="page-title">{{ t('ai.title') }}</h1>
      <div class="page-actions">
        <v-btn :loading="loading" variant="tonal" @click="loadData">
          {{ t('common.refresh') }}
        </v-btn>
      </div>
    </div>

    <v-alert v-if="errorMessage" density="comfortable" type="error" variant="tonal">
      {{ errorMessage }}
    </v-alert>

    <v-card class="page-panel">
      <v-tabs v-model="topTab" color="primary">
        <v-tab value="sources">{{ t('ai.providersTab') }}</v-tab>
        <v-tab value="personas">{{ t('ai.personasTab') }}</v-tab>
        <v-tab value="memories">{{ t('ai.memoryTab') }}</v-tab>
        <v-tab value="relationships">{{ t('ai.relationshipTab') }}</v-tab>
        <v-tab value="profiles">{{ t('ai.personProfileTab') }}</v-tab>
        <v-tab value="skills">{{ t('ai.skillsTab') }}</v-tab>
        <v-tab value="debug">{{ t('ai.debugTab') }}</v-tab>
      </v-tabs>

      <template v-if="topTab === 'sources'">
        <v-card-text>
          <v-tabs v-model="sourceCapabilityTab" class="mb-4" color="primary">
            <v-tab value="chat">{{ t('ai.sourceCapabilityChat') }}</v-tab>
            <v-tab value="embedding">{{ t('ai.sourceCapabilityEmbedding') }}</v-tab>
            <v-tab value="stt">{{ t('ai.sourceCapabilityStt') }}</v-tab>
            <v-tab value="tts">{{ t('ai.sourceCapabilityTts') }}</v-tab>
            <v-tab value="rerank">{{ t('ai.sourceCapabilityRerank') }}</v-tab>
          </v-tabs>

          <template v-if="!sourceCapabilityReady">
            <v-sheet class="surface-gradient-card pa-4" rounded="lg">
              <div class="empty-state-text">{{ t('ai.sourceCapabilityComingSoon') }}</div>
              <div class="empty-state-hint mt-2">{{ t('ai.sourceCapabilityComingSoonHint') }}</div>
            </v-sheet>
          </template>

          <template v-else>
            <v-row>
              <v-col cols="12" lg="4">
                <AISourceListPanel
                  :active-source-id="sourceForm.source_id"
                  :remove-source-item="removeSourceItem"
                  :select-source="selectSource"
                  :source-preset-initial="sourcePresetInitial"
                  :source-preset-label="sourcePresetLabel"
                  :sources="sources"
                  :start-create-source="startCreateSource"
                />
              </v-col>

              <v-col cols="12" lg="8">
                <AISourceWorkspace
                  v-model:source-form="sourceForm"
                  :can-save-source="canSaveSource"
                  :deleting-source="deletingSource"
                  :displayed-source-errors="displayedSourceErrors"
                  :is-creating-source="isCreatingSource"
                  :remove-source="removeSource"
                  :save-source="saveSource"
                  :saving-source="savingSource"
                  :source-preset-label="sourcePresetLabel"
                  :source-preset-options="sourcePresetOptions"
                  :touch-source-field="touchSourceField"
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
                />
              </v-col>
            </v-row>
          </template>
        </v-card-text>
      </template>

      <template v-else-if="topTab === 'personas'">
        <v-card-text>
          <AIPersonasPanel
            v-model:persona-form="personaForm"
            :can-save-persona="canSavePersona"
            :displayed-persona-errors="displayedPersonaErrors"
            :is-creating-persona="isCreatingPersona"
            :persona-bindings="personaBindings"
            :personas="personas"
            :save-persona="savePersona"
            :saving-persona="savingPersona"
            :select-persona="selectPersona"
            :start-create-persona="startCreatePersona"
            :touch-persona-field="touchPersonaField"
          />
        </v-card-text>
      </template>

      <template v-else-if="topTab === 'memories'">
        <v-card-text>
          <AIMemoriesPanel
            v-model:memory-draft="memoryDraft"
            v-model:memory-edit-draft="memoryEditDraft"
            v-model:memory-form="memoryForm"
            :all-memories-selected="allMemoriesSelected"
            :bulk-action-loading="bulkActionLoading"
            :bulk-delete="bulkDeleteMemories"
            :bulk-set-ignored="bulkSetMemoriesIgnored"
            :can-load-memories="canLoadMemories"
            :can-save-edited-memory="canSaveEditedMemory"
            :can-save-memory="canSaveMemory"
            :cancel-edit-memory="cancelEditMemory"
            :clear-selection="clearMemorySelection"
            :deleting-memory-id="deletingMemoryId"
            :editing-memory-id="editingMemoryId"
            :load-memories="loadMemories"
            :load-recent-targets="loadRecentTargets"
            :loading-memories="loadingMemories"
            :loading-recent-targets="loadingRecentTargets"
            :memories="memories"
            :open-chat-view="openChatView"
            :open-debug-conversations="openDebugConversations"
            :recent-targets="recentTargets"
            :remove-memory="removeMemory"
            :save-edited-memory="saveEditedMemory"
            :save-memory="saveMemory"
            :saving-edited-memory-id="savingEditedMemoryId"
            :saving-memory="savingMemory"
            :select-recent-target="selectRecentTarget"
            :selected-memory-count="selectedMemoryCount"
            :selected-memory-ids="selectedMemoryIds"
            :selected-recent-target-id="selectedRecentTargetId"
            :start-edit-memory="startEditMemory"
            :toggle-ignored="toggleMemoryIgnored"
            :toggle-memory-selection="toggleMemorySelection"
            :toggle-select-all="toggleSelectAllMemories"
            :toggling-ignored-id="togglingIgnoredId"
          />
        </v-card-text>
      </template>

      <template v-else-if="topTab === 'relationships'">
        <v-card-text>
          <AIRelationshipsPanel
            v-model:relationship-form="relationshipForm"
            :load-recent-targets="loadRecentTargets"
            :load-relationship-for-target="loadRelationshipForTarget"
            :loading-recent-targets="loadingRecentTargets"
            :loading-relationship-events="loadingRelationshipEvents"
            :loading-selected-relationship="loadingSelectedRelationship"
            :open-chat-view="openChatView"
            :open-debug-conversations="openDebugConversations"
            :recent-targets="recentTargets"
            :relationship="relationship"
            :relationship-events="relationshipEvents"
            :save-relationship="saveRelationship"
            :saving-relationship="savingRelationship"
            :select-relationship="selectRelationship"
          />
        </v-card-text>
      </template>

      <template v-else-if="topTab === 'profiles'">
        <v-card-text>
          <AIPersonProfilesPanel
            v-model:edit-form="personProfileEditForm"
            :add-memory-point="addPersonMemoryPoint"
            :can-save-profile="canSavePersonProfile"
            :deleting-profile-id="deletingPersonProfileId"
            :load-profiles="loadPersonProfiles"
            :loading-profiles="loadingPersonProfiles"
            :person-profile-point-category-options="personProfilePointCategoryOptions"
            :profiles="personProfiles"
            :remove-memory-point="removePersonMemoryPoint"
            :remove-profile="removePersonProfile"
            :save-profile="savePersonProfile"
            :saving-profile="savingPersonProfile"
            :select-profile="selectPersonProfile"
            :selected-person-id="selectedPersonId"
            :selected-profile="selectedPersonProfile"
          />
        </v-card-text>
      </template>

      <template v-else-if="topTab === 'skills'">
        <v-card-text>
          <AISkillsPanel
            :capabilities="skillCapabilities"
            :skills="skills"
          />
        </v-card-text>
      </template>

      <template v-else>
        <v-card-text>
          <AIDebugPanel
            v-model:binding-form="bindingForm"
            v-model:capability-preview-name="capabilityPreviewName"
            v-model:debug-form="debugForm"
            v-model:debug-tab="debugTab"
            v-model:intent-preview-form="intentPreviewForm"
            v-model:preview-form="previewForm"
            :bindings="bindings"
            :cancel-future-task="cancelFutureTask"
            :cancelling-task-id="cancellingTaskId"
            :capabilities="debugCapabilities"
            :capability-preview="capabilityPreview"
            :conversations="conversations"
            :edit-binding="editBinding"
            :editing-binding-id="editingBindingId"
            :future-tasks="futureTasks"
            :intent-preview="intentPreview"
            :latest-assistant-turn="latestAssistantTurn"
            :load-conversation-details="loadConversationDetails"
            :load-debug-data="loadDebugData"
            :load-future-tasks="loadFutureTasks"
            :loading-debug="loadingDebug"
            :loading-future-tasks="loadingFutureTasks"
            :loading-turns="loadingTurns"
            :open-chat-view="openChatView"
            :planning-prompt-channel-sections="planningPromptChannelSections"
            :policy-preview="policyPreview"
            :previewing-capability="previewingCapability"
            :previewing-intents="previewingIntents"
            :previewing-policy="previewingPolicy"
            :prompt-preview="promptPreview"
            :prompt-preview-knowledge-memories="promptPreviewKnowledgeMemories"
            :prompt-preview-long-term-memories="promptPreviewLongTermMemories"
            :prompt-preview-operator-memories="promptPreviewOperatorMemories"
            :prompt-preview-summary-memories="promptPreviewSummaryMemories"
            :reload-all="loadData"
            :remove-binding="removeBinding"
            :reset-binding-form="resetBindingForm"
            :roleplay-prompt-channel-sections="roleplayPromptChannelSections"
            :run-capability-preview="runCapabilityPreview"
            :run-intent-preview="runIntentPreview"
            :run-policy-preview="runPolicyPreview"
            :saving="saving"
            :selected-conversation="selectedConversation"
            :submit-binding="submitBinding"
            :summarize-json-text="summarizeJsonText"
            :summarize-raw-payload="summarizeRawPayload"
            :tool-execution-stats="toolExecutionStats"
            :tool-executions="toolExecutions"
            :trace-ids="traceIds"
            :turns="turns"
          />
        </v-card-text>
      </template>

    </v-card>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { getErrorMessage } from '@/api/client'
  import { useAIDebugTab } from '@/composables/useAIDebugTab'
  import { useAIDebugToolsTab } from '@/composables/useAIDebugToolsTab'
  import { useAIFutureTasksTab } from '@/composables/useAIFutureTasksTab'
  import { useAIMemoryTab } from '@/composables/useAIMemoryTab'
  import { useAIModelsTab } from '@/composables/useAIModelsTab'
  import { useAIPersonasTab } from '@/composables/useAIPersonasTab'
  import { useAIPersonProfilesTab } from '@/composables/useAIPersonProfilesTab'
  import { useAIRelationshipTab } from '@/composables/useAIRelationshipTab'
  import { useAISkillsTab } from '@/composables/useAISkillsTab'
  import AIDebugPanel from '@/views/ai/AIDebugPanel.vue'
  import AIMemoriesPanel from '@/views/ai/AIMemoriesPanel.vue'
  import AIPersonasPanel from '@/views/ai/AIPersonasPanel.vue'
  import AIPersonProfilesPanel from '@/views/ai/AIPersonProfilesPanel.vue'
  import AIRelationshipsPanel from '@/views/ai/AIRelationshipsPanel.vue'
  import AISkillsPanel from '@/views/ai/AISkillsPanel.vue'
  import AISourceListPanel from '@/views/ai/AISourceListPanel.vue'
  import AISourceModelsPanel from '@/views/ai/AISourceModelsPanel.vue'
  import AISourceWorkspace from '@/views/ai/AISourceWorkspace.vue'
  import '@/views/ai/panelShared.css'

  const { t } = useI18n()
  const router = useRouter()

  const loading = ref(false)
  const errorMessage = ref('')
  const topTab = ref('sources')
  const debugTab = ref('conversations')
  const sourceCapabilityTab = ref('chat')

  const {
    conversations,
    debugForm,
    latestAssistantTurn,
    loadConversationDetails,
    loadDebugData,
    loadingDebug,
    loadingTurns,
    planningPromptChannelSections,
    promptPreview,
    promptPreviewKnowledgeMemories,
    promptPreviewLongTermMemories,
    promptPreviewOperatorMemories,
    promptPreviewSummaryMemories,
    roleplayPromptChannelSections,
    selectedConversation,
    summarizeJsonText,
    summarizeRawPayload,
    toolExecutions,
    toolExecutionStats,
    traceIds,
    turns,
  } = useAIDebugTab(t)

  const {
    capabilities: skillCapabilities,
    loadSkillsData,
    skills,
  } = useAISkillsTab()

  const {
    bindingForm,
    bindings,
    capabilities: debugCapabilities,
    capabilityPreview,
    capabilityPreviewName,
    editBinding,
    editingBindingId,
    intentPreview,
    intentPreviewForm,
    loadDebugToolsData,
    policyPreview,
    previewForm,
    previewingCapability,
    previewingIntents,
    previewingPolicy,
    removeBinding,
    resetBindingForm,
    runCapabilityPreview,
    runIntentPreview,
    runPolicyPreview,
    saving,
    submitBinding,
  } = useAIDebugToolsTab(t)

  const {
    canSavePersona,
    displayedPersonaErrors,
    isCreatingPersona,
    loadPersonasData,
    personaBindings,
    personaForm,
    personas,
    savePersona,
    savingPersona,
    selectPersona,
    startCreatePersona,
    touchPersonaField,
  } = useAIPersonasTab(t)

  const {
    canFetchSourceModels,
    canSaveModel,
    canSaveProfile,
    canSaveSource,
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
    sourceForm,
    sourceModels,
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
  } = useAIModelsTab(sourceCapabilityTab, t)

  const sourceCapabilityReady = computed(() => (
    sourceCapabilityTab.value === 'chat'
    || sourceCapabilityTab.value === 'embedding'
    || sourceCapabilityTab.value === 'stt'
    || sourceCapabilityTab.value === 'tts'
    || sourceCapabilityTab.value === 'rerank'
  ))

  const {
    cancelFutureTask,
    cancellingTaskId,
    futureTasks,
    loadFutureTasks,
    loadingFutureTasks,
  } = useAIFutureTasksTab(t)

  const {
    allMemoriesSelected,
    bulkActionLoading,
    bulkDelete: bulkDeleteMemories,
    bulkSetIgnored: bulkSetMemoriesIgnored,
    canLoadMemories,
    canSaveMemory,
    canSaveEditedMemory,
    cancelEditMemory,
    clearSelection: clearMemorySelection,
    deletingMemoryId,
    editingMemoryId,
    loadMemories,
    loadRecentTargets,
    loadingMemories,
    loadingRecentTargets,
    memoryEditDraft,
    memories,
    memoryDraft,
    memoryForm,
    recentTargets,
    removeMemory,
    saveMemory,
    saveEditedMemory,
    savingEditedMemoryId,
    savingMemory,
    selectedMemoryCount,
    selectedMemoryIds,
    selectRecentTarget,
    selectedRecentTargetId,
    startEditMemory,
    toggleIgnored: toggleMemoryIgnored,
    toggleMemorySelection,
    toggleSelectAll: toggleSelectAllMemories,
    togglingIgnoredId,
  } = useAIMemoryTab(t)

  const {
    loadRelationshipForTarget,
    loadingRelationshipEvents,
    loadRelationships,
    loadingSelectedRelationship,
    relationship,
    relationshipEvents,
    relationshipForm,
    saveRelationship,
    savingRelationship,
    selectRelationship,
  } = useAIRelationshipTab(t)

  const {
    addMemoryPoint: addPersonMemoryPoint,
    canSaveProfile: canSavePersonProfile,
    deletingProfileId: deletingPersonProfileId,
    editForm: personProfileEditForm,
    loadProfiles: loadPersonProfiles,
    loadingProfiles: loadingPersonProfiles,
    profiles: personProfiles,
    removeMemoryPoint: removePersonMemoryPoint,
    removeProfile: removePersonProfile,
    saveProfile: savePersonProfile,
    savingProfile: savingPersonProfile,
    selectProfile: selectPersonProfile,
    selectedPersonId,
    selectedProfile: selectedPersonProfile,
  } = useAIPersonProfilesTab(t)

  const sourcePresetOptions = computed(() => sourcePresets.value.map(item => ({
    title: item.display_name,
    value: item.preset_type,
  })))

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

  const personProfilePointCategoryOptions = computed(() => [
    { title: t('ai.personProfileCategoryFact'), value: 'fact' },
    { title: t('ai.personProfileCategoryPreference'), value: 'preference' },
    { title: t('ai.personProfileCategoryRelationship'), value: 'relationship' },
    { title: t('ai.personProfileCategoryImpression'), value: 'impression' },
  ])

  function openDebugConversations () {
    topTab.value = 'debug'
    debugTab.value = 'conversations'
  }

  async function openChatView () {
    await router.push({ name: 'chat' })
  }

  async function loadData () {
    loading.value = true
    errorMessage.value = ''
    try {
      await Promise.all([
        loadDebugData(),
        loadSkillsData(),
        loadDebugToolsData(),
        loadPersonasData(),
        loadModelsData(),
        loadFutureTasks(),
        loadRelationships(),
        loadRecentTargets(),
        loadPersonProfiles(),
      ])
    } catch (error) {
      errorMessage.value = getErrorMessage(error, t('ai.loadFailed'))
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    void loadData()
  })
</script>

<style scoped>
:deep(.page-table .v-data-table-footer__info) {
  display: none;
}
</style>
