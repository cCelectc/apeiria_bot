<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.debug')"
    :title="t('ai.debugTab')"
  >
    <template #actions>
      <v-btn :loading="loading" variant="tonal" @click="loadData">
        {{ t('common.refresh') }}
      </v-btn>
    </template>

    <v-card class="page-panel">
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
    </v-card>
  </PageScaffold>
</template>

<script setup lang="ts">
  import type { AIDebugRouteValue } from '@/views/ai/routeState'
  import { onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import { PageScaffold } from '@/components/workbench'
  import { useAIDebugTab } from '@/composables/useAIDebugTab'
  import { useAIDebugToolsTab } from '@/composables/useAIDebugToolsTab'
  import { useAIFutureTasksTab } from '@/composables/useAIFutureTasksTab'
  import { useAISkillsTab } from '@/composables/useAISkillsTab'
  import AIDebugPanel from '@/views/ai/AIDebugPanel.vue'
  import { useAIPageLoader } from '@/views/ai/pageHelpers'
  import { normalizeAIDebugRouteValue } from '@/views/ai/routeState'
  import '@/views/ai/panelShared.css'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  let applyingRouteState = false
  const debugTab = ref<AIDebugRouteValue>('conversations')
  const { errorMessage, loading, runPageLoad } = useAIPageLoader(() => t('ai.loadFailed'))

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
    loadSkillsData,
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
    cancelFutureTask,
    cancellingTaskId,
    futureTasks,
    loadFutureTasks,
    loadingFutureTasks,
  } = useAIFutureTasksTab(t)

  function applyRouteState () {
    const nextDebugTab = normalizeAIDebugRouteValue(route.query.debug)
    if (debugTab.value === nextDebugTab) {
      return
    }
    applyingRouteState = true
    debugTab.value = nextDebugTab
    applyingRouteState = false
  }

  function syncRouteQuery () {
    if (route.query.debug === debugTab.value) {
      return
    }
    void router.replace({ query: { debug: debugTab.value } })
  }

  async function openChatView () {
    await router.push({ name: 'chat' })
  }

  async function loadData () {
    await runPageLoad(async () => {
      await Promise.all([
        loadDebugData(),
        loadDebugToolsData(),
        loadFutureTasks(),
        loadSkillsData(),
      ])
    })
  }

  applyRouteState()

  onMounted(() => {
    applyRouteState()
    void loadData()
  })

  watch(() => route.query.debug, () => {
    applyRouteState()
  })

  watch(debugTab, () => {
    if (applyingRouteState) return
    syncRouteQuery()
  }, { flush: 'sync' })
</script>
