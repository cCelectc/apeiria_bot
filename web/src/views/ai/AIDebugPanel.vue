<template>
  <div class="ai-debug-layout">
    <div :aria-label="t('ai.debugTab')" class="ai-debug-nav" role="navigation">
      <button
        v-for="item in debugSectionOptions"
        :key="item.value"
        :aria-current="debugTab === item.value ? 'page' : undefined"
        class="ai-debug-nav__item"
        :class="{ 'ai-debug-nav__item--active': debugTab === item.value }"
        type="button"
        @click="debugTab = item.value"
      >
        <v-icon :icon="item.icon" size="20" />
        <span>{{ item.title }}</span>
      </button>
    </div>

    <div class="ai-debug-content">
      <template v-if="debugTab === 'conversations'">
        <div class="d-flex flex-column ga-5">
          <div class="ai-binding-form">
            <v-text-field
              v-model.number="debugForm.limit"
              density="comfortable"
              hide-details
              :label="t('ai.workbenchConversationLimit')"
              min="1"
              type="number"
            />
            <v-text-field
              v-model.number="debugForm.turnLimit"
              density="comfortable"
              hide-details
              :label="t('ai.workbenchTurnLimit')"
              min="1"
              type="number"
            />
          </div>

          <div class="d-flex flex-wrap justify-space-between align-center ga-3">
            <div class="d-flex flex-wrap ga-2">
              <v-chip color="primary" size="small" variant="tonal">
                {{ t('ai.debugConversationTitle') }}: {{ conversations.length }}
              </v-chip>
              <v-chip color="primary" size="small" variant="tonal">
                {{ t('ai.debugMessageCount') }}: {{ turns.length }}
              </v-chip>
              <v-chip color="primary" size="small" variant="tonal">
                {{ t('ai.debugToolCallCount') }}: {{ toolExecutions.length }}
              </v-chip>
            </div>
            <v-btn color="primary" :loading="loadingDebug" @click="loadDebugData">
              {{ t('ai.loadWorkbench') }}
            </v-btn>
          </div>

          <v-sheet v-if="conversations.length > 0" class="surface-gradient-card pa-4">
            <div v-if="selectedConversation" class="d-flex flex-column ga-2 text-body-2">
              <div>{{ t('ai.conversationId') }}: {{ selectedConversation.session_id }}</div>
              <div>{{ t('ai.scopeType') }}: {{ selectedConversation.scene_type }}</div>
              <div>{{ t('ai.scopeId') }}: {{ selectedConversation.scene_id }}</div>
              <div>{{ t('ai.scopeUser') }}: {{ selectedConversation.subject_id || t('common.none') }}</div>
              <div>{{ t('ai.conversationSummary') }}: {{ selectedConversation.summary_text || t('common.none') }}</div>
              <div>{{ t('ai.lastActiveAt') }}: {{ selectedConversation.last_message_at }}</div>
            </div>
            <div v-else class="empty-state-text">
              {{ t('ai.noConversationSelected') }}
            </div>
          </v-sheet>

          <template v-if="conversations.length === 0 && !loadingDebug">
            <v-sheet class="surface-gradient-card pa-4">
              <div class="empty-state-text mb-3">{{ t('ai.noConversationSelected') }}</div>
              <div class="empty-state-hint mb-3">{{ t('ai.noConversationSelectedHint') }}</div>
              <div class="d-flex flex-wrap ga-3">
                <v-btn color="primary" variant="tonal" @click="openChatView">
                  {{ t('ai.goToChatView') }}
                </v-btn>
              </div>
            </v-sheet>
          </template>

          <template v-else>
            <v-row>
              <v-col cols="12" lg="5">
                <v-data-table
                  class="page-table"
                  density="compact"
                  :headers="conversationHeaders"
                  :items="conversations"
                  :items-per-page-text="t('common.itemsPerPage')"
                  :loading="loadingDebug"
                  :no-data-text="t('common.noData')"
                >
                  <template #item.session_id="{ item }">
                    <v-btn
                      color="primary"
                      size="small"
                      variant="text"
                      @click="loadConversationDetails(item.session_id)"
                    >
                      {{ item.session_id.slice(0, 16) }}...
                    </v-btn>
                  </template>
                </v-data-table>
              </v-col>

              <v-col cols="12" lg="7">
                <v-sheet class="surface-gradient-card pa-4 mb-4">
                  <div v-if="traceIds.length > 0" class="d-flex flex-wrap ga-2">
                    <v-chip
                      v-for="traceId in traceIds"
                      :key="traceId"
                      color="primary"
                      size="small"
                      variant="tonal"
                    >
                      {{ traceId }}
                    </v-chip>
                  </div>
                  <div v-else class="empty-state-text">
                    {{ t('ai.noTraceIds') }}
                  </div>
                </v-sheet>

                <v-sheet class="surface-gradient-card pa-4">
                  <div class="d-flex flex-wrap ga-2">
                    <v-chip color="success" size="small" variant="tonal">
                      {{ t('ai.toolStatusSuccess') }}: {{ toolExecutionStats.success }}
                    </v-chip>
                    <v-chip color="error" size="small" variant="tonal">
                      {{ t('ai.toolStatusError') }}: {{ toolExecutionStats.error }}
                    </v-chip>
                    <v-chip color="warning" size="small" variant="tonal">
                      {{ t('ai.toolStatusTimeout') }}: {{ toolExecutionStats.timeout }}
                    </v-chip>
                  </div>
                </v-sheet>

                <v-sheet class="surface-gradient-card pa-4 mt-4">
                  <div class="text-subtitle-2 font-weight-medium mb-3">
                    {{ t('ai.finalReplyTitle') }}
                  </div>
                  <div v-if="latestAssistantTurn" class="d-flex flex-column ga-3 text-body-2">
                    <div>{{ latestAssistantTurn.text_content }}</div>
                    <div>{{ t('ai.finalReplyModel') }}: {{ latestAssistantTurn.model_name || t('common.none') }}</div>
                    <div>{{ t('ai.finalReplySource') }}: {{ latestAssistantTurn.source_id || t('common.none') }}</div>
                    <div>{{ t('ai.finalReplyTraceId') }}: {{ latestAssistantTurn.trace_id || t('common.none') }}</div>
                  </div>
                  <div v-else class="empty-state-text">
                    {{ t('common.noData') }}
                  </div>
                </v-sheet>
              </v-col>
            </v-row>

            <v-sheet class="surface-gradient-card pa-4">
              <div v-if="promptPreview" class="d-flex flex-column ga-3 text-body-2">
                <div>{{ t('ai.latestUserMessage') }}: {{ promptPreview.latest_user_message || t('common.none') }}</div>
                <div>{{ t('ai.conversationId') }}: {{ promptPreview.session_id }}</div>
                <div>{{ t('ai.planningModel') }}: {{ promptPreview.planning_model_name || promptPreview.model_name || t('common.none') }}</div>
                <div>{{ t('ai.planningSource') }}: {{ promptPreview.planning_source_id || t('common.none') }}</div>
                <div>{{ t('ai.planningProfile') }}: {{ promptPreview.planning_profile_id || t('common.none') }}</div>
                <div>{{ t('ai.modelTaskClass') }}: {{ promptPreview.planning_task_class || t('common.none') }}</div>
                <div>{{ t('ai.roleplayModel') }}: {{ promptPreview.roleplay_model_name || t('common.none') }}</div>
                <div>{{ t('ai.roleplaySource') }}: {{ promptPreview.roleplay_source_id || t('common.none') }}</div>
                <div>{{ t('ai.roleplayProfile') }}: {{ promptPreview.roleplay_profile_id || t('common.none') }}</div>
                <div>{{ t('ai.modelTaskClass') }}: {{ promptPreview.roleplay_task_class || t('common.none') }}</div>
                <div>{{ t('ai.personaId') }}: {{ promptPreview.persona_id || t('common.none') }}</div>
                <div>{{ t('ai.relationshipStateTitle') }}: {{ promptPreview.relationship_context || t('common.none') }}</div>
                <div>{{ t('ai.toolPolicyTitle') }}: {{ promptPreview.tool_policy || t('common.none') }}</div>
                <div>{{ t('ai.socialAction') }}: {{ promptPreview.social_action || t('common.none') }}</div>
                <div>{{ t('ai.socialToolMode') }}: {{ promptPreview.social_tool_mode || t('common.none') }}</div>
                <div>{{ t('ai.socialReason') }}: {{ promptPreview.social_reason_text || t('common.none') }}</div>
                <div>{{ t('ai.socialReasonCodes') }}: {{ promptPreview.social_reason_codes.join(', ') || t('common.none') }}</div>
                <div>{{ t('ai.socialPolicySource') }}: {{ promptPreview.social_policy_source || t('common.none') }}</div>
                <div>{{ t('ai.conversationSummary') }}: {{ promptPreview.conversation_summary || t('common.none') }}</div>
                <div>{{ t('ai.memoryHits') }}: {{ promptPreview.memories.length }}</div>
                <div>{{ t('ai.memoryLayerOperator') }}: {{ promptPreview.operator_memory_count }}</div>
                <div>{{ t('ai.memoryLayerSummary') }}: {{ promptPreview.summary_memory_count }}</div>
                <div>{{ t('ai.memoryLayerLongTerm') }}: {{ promptPreview.long_term_memory_count }}</div>
                <div>{{ t('ai.memoryLayerKnowledge') }}: {{ promptPreview.knowledge_memory_count }}</div>
                <div>{{ t('ai.toolResultsTitle') }}: {{ promptPreview.tool_results.length }}</div>
                <div class="text-subtitle-2 font-weight-medium mt-2">{{ t('ai.promptPreviewPlanning') }}</div>
                <pre class="ai-prompt-preview">{{ promptPreview.rendered_prompt }}</pre>
                <v-expansion-panels class="mt-2" multiple variant="accordion">
                  <v-expansion-panel
                    v-for="section in planningPromptChannelSections"
                    :key="`planning-${section.key}`"
                  >
                    <v-expansion-panel-title>
                      <div class="d-flex align-center justify-space-between w-100">
                        <span>{{ section.title }}</span>
                        <v-chip color="primary" size="x-small" variant="tonal">
                          {{ section.lines.length }}
                        </v-chip>
                      </div>
                    </v-expansion-panel-title>
                    <v-expansion-panel-text>
                      <pre class="ai-prompt-preview">{{ section.lines.join('\n') }}</pre>
                    </v-expansion-panel-text>
                  </v-expansion-panel>
                </v-expansion-panels>
                <div class="text-subtitle-2 font-weight-medium mt-2">{{ t('ai.promptPreviewRoleplay') }}</div>
                <pre class="ai-prompt-preview">{{ promptPreview.rendered_roleplay_prompt || t('common.none') }}</pre>
                <v-expansion-panels
                  v-if="roleplayPromptChannelSections.length > 0"
                  class="mt-2"
                  multiple
                  variant="accordion"
                >
                  <v-expansion-panel
                    v-for="section in roleplayPromptChannelSections"
                    :key="`roleplay-${section.key}`"
                  >
                    <v-expansion-panel-title>
                      <div class="d-flex align-center justify-space-between w-100">
                        <span>{{ section.title }}</span>
                        <v-chip color="secondary" size="x-small" variant="tonal">
                          {{ section.lines.length }}
                        </v-chip>
                      </div>
                    </v-expansion-panel-title>
                    <v-expansion-panel-text>
                      <pre class="ai-prompt-preview">{{ section.lines.join('\n') }}</pre>
                    </v-expansion-panel-text>
                  </v-expansion-panel>
                </v-expansion-panels>
              </div>
              <div v-else class="empty-state-text">
                {{ t('ai.noPromptPreview') }}
              </div>
            </v-sheet>

            <v-sheet class="surface-gradient-card pa-4">
              <div class="text-subtitle-2 font-weight-medium mb-3">
                {{ t('ai.memoryLayerOperator') }} · {{ promptPreviewOperatorMemories.length }}
              </div>
              <v-data-table
                class="page-table"
                density="compact"
                :headers="promptMemoryHeaders"
                :items="promptPreviewOperatorMemories"
                :items-per-page-text="t('common.itemsPerPage')"
                :no-data-text="t('common.noData')"
              />
            </v-sheet>

            <v-sheet class="surface-gradient-card pa-4">
              <div class="text-subtitle-2 font-weight-medium mb-3">
                {{ t('ai.memoryLayerSummary') }} · {{ promptPreviewSummaryMemories.length }}
              </div>
              <v-data-table
                class="page-table"
                density="compact"
                :headers="promptMemoryHeaders"
                :items="promptPreviewSummaryMemories"
                :items-per-page-text="t('common.itemsPerPage')"
                :no-data-text="t('common.noData')"
              />
            </v-sheet>

            <v-sheet class="surface-gradient-card pa-4">
              <div class="text-subtitle-2 font-weight-medium mb-3">
                {{ t('ai.memoryLayerLongTerm') }} · {{ promptPreviewLongTermMemories.length }}
              </div>
              <v-data-table
                class="page-table"
                density="compact"
                :headers="promptMemoryHeaders"
                :items="promptPreviewLongTermMemories"
                :items-per-page-text="t('common.itemsPerPage')"
                :no-data-text="t('common.noData')"
              />
            </v-sheet>

            <v-sheet class="surface-gradient-card pa-4">
              <div class="text-subtitle-2 font-weight-medium mb-3">
                {{ t('ai.memoryLayerKnowledge') }} · {{ promptPreviewKnowledgeMemories.length }}
              </div>
              <v-data-table
                class="page-table"
                density="compact"
                :headers="promptMemoryHeaders"
                :items="promptPreviewKnowledgeMemories"
                :items-per-page-text="t('common.itemsPerPage')"
                :no-data-text="t('common.noData')"
              />
            </v-sheet>

            <v-data-table
              class="page-table"
              density="compact"
              :headers="turnHeaders"
              :items="turns"
              :items-per-page-text="t('common.itemsPerPage')"
              :loading="loadingTurns"
              :no-data-text="t('common.noData')"
            >
              <template #item.text_content="{ value }">
                <span class="ai-turn-content">{{ value }}</span>
              </template>
              <template #item.meta="{ item }">
                <span class="text-medium-emphasis">{{ summarizeRawPayload(item.meta || item.raw_data) }}</span>
              </template>
            </v-data-table>

            <v-data-table
              class="page-table"
              density="compact"
              :headers="toolExecutionHeaders"
              :items="toolExecutions"
              :items-per-page-text="t('common.itemsPerPage')"
              :loading="loadingTurns"
              :no-data-text="t('common.noData')"
            >
              <template #item.status="{ value }">
                <v-chip
                  :color="value === 'success' ? 'success' : value === 'timeout' ? 'warning' : 'error'"
                  size="x-small"
                  variant="tonal"
                >
                  {{ value }}
                </v-chip>
              </template>
              <template #item.input_json="{ value }">
                <span class="text-medium-emphasis">{{ summarizeJsonText(value) }}</span>
              </template>
              <template #item.output_json="{ value }">
                <span class="text-medium-emphasis">{{ summarizeJsonText(value) }}</span>
              </template>
            </v-data-table>
          </template>
        </div>
      </template>

      <template v-else-if="debugTab === 'futureTasks'">
        <div class="d-flex flex-column ga-4">
          <div class="d-flex justify-end">
            <v-btn color="primary" :loading="loadingFutureTasks" @click="loadFutureTasks">
              {{ t('ai.loadFutureTasks') }}
            </v-btn>
          </div>

          <v-data-table
            class="page-table"
            density="compact"
            :headers="futureTaskHeaders"
            :items="futureTasks"
            :items-per-page-text="t('common.itemsPerPage')"
            :loading="loadingFutureTasks"
            :no-data-text="t('common.noData')"
          >
            <template #item.status="{ value }">
              <v-chip
                :color="value === 'pending' ? 'primary' : value === 'sent' ? 'success' : value === 'cancelled' ? 'default' : 'error'"
                size="x-small"
                variant="tonal"
              >
                {{ value }}
              </v-chip>
            </template>
            <template #item.actions="{ item }">
              <div class="d-flex justify-end">
                <v-btn
                  v-if="item.status === 'pending'"
                  color="error"
                  :loading="cancellingTaskId === item.task_id"
                  size="small"
                  variant="text"
                  @click="cancelFutureTask(item.task_id)"
                >
                  {{ t('common.cancel') }}
                </v-btn>
              </div>
            </template>
          </v-data-table>
        </div>
      </template>

      <template v-else>
        <div class="d-flex flex-column ga-4">
          <div class="text-body-2 text-medium-emphasis">
            {{ t('ai.advancedDebugHint') }}
          </div>

          <div class="ai-binding-form">
            <v-select
              v-model="bindingForm.scope_type"
              density="comfortable"
              hide-details
              :items="scopeOptions"
              :label="t('ai.scopeType')"
            />
            <v-text-field
              v-model.trim="bindingForm.scope_id"
              density="comfortable"
              hide-details
              :label="t('ai.scopeId')"
            />
            <v-switch
              v-model="bindingForm.allow_read_only_tools"
              color="primary"
              density="comfortable"
              hide-details
              :label="t('ai.allowReadOnlyTools')"
            />
            <v-select
              v-model="bindingForm.capability_mode"
              density="comfortable"
              hide-details
              :items="capabilityModeOptions"
              :label="t('ai.capabilityMode')"
            />
          </div>

          <div class="d-flex ga-3 justify-end">
            <v-btn
              v-if="editingBindingId"
              :loading="saving"
              variant="text"
              @click="resetBindingForm"
            >
              {{ t('common.cancel') }}
            </v-btn>
            <v-btn color="primary" :loading="saving" @click="submitBinding(reloadAll)">
              {{ editingBindingId ? t('ai.updateBinding') : t('ai.createBinding') }}
            </v-btn>
          </div>

          <v-data-table
            class="page-table"
            density="compact"
            :headers="bindingHeaders"
            :items="bindings"
            :items-per-page-text="t('common.itemsPerPage')"
            :no-data-text="t('common.noData')"
          >
            <template #item.allow_read_only_tools="{ value }">
              <v-chip :color="value ? 'success' : 'default'" size="x-small" variant="tonal">
                {{ value ? t('ai.enabled') : t('ai.disabled') }}
              </v-chip>
            </template>
            <template #item.actions="{ item }">
              <div class="d-flex ga-2 justify-end">
                <v-btn
                  color="primary"
                  icon="mdi-pencil-outline"
                  size="small"
                  variant="text"
                  @click="editBinding(item)"
                />
                <v-btn
                  color="error"
                  icon="mdi-delete-outline"
                  size="small"
                  variant="text"
                  @click="removeBinding(item.binding_id, reloadAll)"
                />
              </div>
            </template>
          </v-data-table>

          <div class="ai-binding-form">
            <v-select
              v-model="previewForm.scope_type"
              density="comfortable"
              hide-details
              :items="scopeOptions"
              :label="t('ai.scopeType')"
            />
            <v-switch
              v-model="previewForm.is_tome"
              color="primary"
              density="comfortable"
              hide-details
              :label="t('ai.isTome')"
            />
            <v-switch
              v-model="previewForm.allow_read_only_tools"
              color="primary"
              density="comfortable"
              hide-details
              :label="t('ai.allowReadOnlyTools')"
            />
            <v-select
              v-model="previewForm.capability_mode"
              density="comfortable"
              hide-details
              :items="capabilityModeOptions"
              :label="t('ai.capabilityMode')"
            />
            <v-select
              v-model="capabilityPreviewName"
              density="comfortable"
              hide-details
              item-title="capability_name"
              item-value="capability_name"
              :items="capabilities"
              :label="t('ai.capabilityName')"
            />
            <v-text-field
              v-model.trim="intentPreviewForm.message_text"
              density="comfortable"
              hide-details
              :label="t('ai.intentPreviewMessage')"
            />
          </div>

          <div class="d-flex ga-3 justify-end">
            <v-btn :loading="previewingPolicy" variant="tonal" @click="runPolicyPreview">
              {{ t('ai.previewPolicy') }}
            </v-btn>
            <v-btn :loading="previewingIntents" variant="tonal" @click="runIntentPreview">
              {{ t('ai.previewIntents') }}
            </v-btn>
            <v-btn color="primary" :loading="previewingCapability" @click="runCapabilityPreview">
              {{ t('ai.previewCapability') }}
            </v-btn>
          </div>

          <v-sheet class="surface-gradient-card pa-4">
            <div v-if="policyPreview" class="d-flex flex-column ga-2 text-body-2">
              <div>{{ t('ai.executionEnabled') }}: {{ policyPreview.execution_enabled ? t('ai.enabled') : t('ai.disabled') }}</div>
              <div>{{ t('ai.allowCapabilityBridge') }}: {{ policyPreview.allow_capability_bridge ? t('ai.enabled') : t('ai.disabled') }}</div>
              <div>{{ t('ai.allowedTools') }}: {{ policyPreview.allowed_tool_names?.join(', ') || t('common.none') }}</div>
            </div>
            <div v-else class="empty-state-text">
              {{ t('ai.noPreviewYet') }}
            </div>
          </v-sheet>

          <v-sheet class="surface-gradient-card pa-4">
            <div v-if="capabilityPreview" class="d-flex flex-column ga-2 text-body-2">
              <div>{{ t('ai.capabilityName') }}: {{ capabilityPreview.capability_name }}</div>
              <div>{{ t('ai.registered') }}: {{ capabilityPreview.registered ? t('ai.enabled') : t('ai.disabled') }}</div>
              <div>{{ t('ai.allowed') }}: {{ capabilityPreview.allowed ? t('ai.enabled') : t('ai.disabled') }}</div>
              <div>{{ t('ai.reason') }}: {{ capabilityPreview.reason }}</div>
            </div>
            <div v-else class="empty-state-text">
              {{ t('ai.noPreviewYet') }}
            </div>
          </v-sheet>

          <v-data-table
            class="page-table"
            density="compact"
            :headers="intentPreviewHeaders"
            :items="intentPreview"
            :items-per-page-text="t('common.itemsPerPage')"
            :no-data-text="t('common.noData')"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
  import type {
    AICapabilityItem,
    AICapabilityPreviewItem,
    AIChatMessageItem,
    AIFutureTaskItem,
    AIMemoryItem,
    AISessionItem,
    AISessionPromptPreviewItem,
    AIToolExecutionItem,
    AIToolIntentPreviewItem,
    AIToolPolicyBindingItem,
    AIToolPolicyPreviewItem,
  } from '@/api/ai/types'
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'

  interface PromptChannelSection {
    key: string
    title: string
    lines: string[]
  }

  interface DebugFormState {
    limit: number
    turnLimit: number
  }

  interface BindingFormState {
    scope_type: string
    scope_id: string
    allow_read_only_tools: boolean
    capability_mode: string
  }

  interface PreviewFormState {
    scope_type: string
    is_tome: boolean
    allow_read_only_tools: boolean
    capability_mode: string
  }

  interface IntentPreviewFormState {
    message_text: string
  }

  defineProps<{
    bindings: AIToolPolicyBindingItem[]
    capabilities: AICapabilityItem[]
    capabilityPreview: AICapabilityPreviewItem | null
    cancelFutureTask: (taskId: string) => void | Promise<void>
    cancellingTaskId: string
    conversations: AISessionItem[]
    editBinding: (item: AIToolPolicyBindingItem) => void
    editingBindingId: string
    futureTasks: AIFutureTaskItem[]
    intentPreview: AIToolIntentPreviewItem[]
    latestAssistantTurn: AIChatMessageItem | null
    loadConversationDetails: (sceneId: string) => void | Promise<void>
    loadDebugData: () => void | Promise<void>
    loadFutureTasks: () => void | Promise<void>
    loadingDebug: boolean
    loadingFutureTasks: boolean
    loadingTurns: boolean
    openChatView: () => void | Promise<void>
    planningPromptChannelSections: PromptChannelSection[]
    policyPreview: AIToolPolicyPreviewItem | null
    previewingCapability: boolean
    previewingIntents: boolean
    previewingPolicy: boolean
    promptPreview: AISessionPromptPreviewItem | null
    promptPreviewKnowledgeMemories: AIMemoryItem[]
    promptPreviewLongTermMemories: AIMemoryItem[]
    promptPreviewOperatorMemories: AIMemoryItem[]
    promptPreviewSummaryMemories: AIMemoryItem[]
    reloadAll: () => Promise<void>
    removeBinding: (bindingId: string, reload: () => Promise<void>) => void | Promise<void>
    resetBindingForm: () => void
    roleplayPromptChannelSections: PromptChannelSection[]
    runCapabilityPreview: () => void | Promise<void>
    runIntentPreview: () => void | Promise<void>
    runPolicyPreview: () => void | Promise<void>
    saving: boolean
    selectedConversation: AISessionItem | null
    submitBinding: (reload: () => Promise<void>) => void | Promise<void>
    summarizeJsonText: (value: string | null) => string
    summarizeRawPayload: (payload: Record<string, unknown> | null) => string
    toolExecutions: AIToolExecutionItem[]
    toolExecutionStats: {
      success: number
      error: number
      timeout: number
    }
    traceIds: string[]
    turns: AIChatMessageItem[]
  }>()

  const debugTab = defineModel<string>('debugTab', { required: true })
  const debugForm = defineModel<DebugFormState>('debugForm', { required: true })
  const bindingForm = defineModel<BindingFormState>('bindingForm', { required: true })
  const previewForm = defineModel<PreviewFormState>('previewForm', { required: true })
  const intentPreviewForm = defineModel<IntentPreviewFormState>('intentPreviewForm', { required: true })
  const capabilityPreviewName = defineModel<string>('capabilityPreviewName', { required: true })

  const { t } = useI18n()

  const scopeOptions = computed(() => [
    { title: t('ai.scopeConversation'), value: 'conversation' },
    { title: t('ai.scopeUser'), value: 'user' },
    { title: t('ai.scopeGroup'), value: 'group' },
    { title: t('ai.scopeGlobal'), value: 'global' },
  ])

  const capabilityModeOptions = computed(() => [
    { title: t('ai.capabilityModeOff'), value: 'off' },
    { title: t('ai.capabilityModePrivateOnly'), value: 'private_only' },
    { title: t('ai.capabilityModeDirectOnly'), value: 'direct_only' },
  ])
  const debugSectionOptions = computed(() => [
    { icon: 'mdi-message-text-outline', title: t('ai.debugConversationTitle'), value: 'conversations' },
    { icon: 'mdi-calendar-clock-outline', title: t('ai.futureTaskTab'), value: 'futureTasks' },
    { icon: 'mdi-tools', title: t('ai.debugToolsTab'), value: 'tools' },
  ])

  const bindingHeaders = computed(() => [
    { title: t('ai.scopeType'), key: 'scope_type', sortable: false },
    { title: t('ai.scopeId'), key: 'scope_id', sortable: false },
    { title: t('ai.allowReadOnlyTools'), key: 'allow_read_only_tools', sortable: false },
    { title: t('ai.capabilityMode'), key: 'capability_mode', sortable: false },
    { title: t('common.actions'), key: 'actions', sortable: false, align: 'end' as const },
  ])

  const intentPreviewHeaders = computed(() => [
    { title: t('ai.toolName'), key: 'tool_name', sortable: false },
    { title: t('ai.intentKind'), key: 'kind', sortable: false },
    { title: t('ai.reason'), key: 'reason', sortable: false },
  ])

  const conversationHeaders = computed(() => [
    { title: t('ai.conversationId'), key: 'session_id', sortable: false },
    { title: t('ai.scopeType'), key: 'scene_type', sortable: false },
    { title: t('ai.scopeId'), key: 'scene_id', sortable: false },
    { title: t('ai.scopeUser'), key: 'subject_id', sortable: false },
    { title: t('ai.conversationSummary'), key: 'summary_text', sortable: false },
    { title: t('ai.lastActiveAt'), key: 'last_message_at', sortable: false },
  ])

  const turnHeaders = computed(() => [
    { title: t('ai.turnSender'), key: 'author_role', sortable: false },
    { title: t('ai.turnContent'), key: 'text_content', sortable: false },
    { title: t('ai.traceId'), key: 'trace_id', sortable: false },
    { title: t('ai.modelName'), key: 'model_name', sortable: false },
    { title: t('ai.turnRawPayload'), key: 'meta', sortable: false },
  ])

  const toolExecutionHeaders = computed(() => [
    { title: t('ai.toolName'), key: 'tool_name', sortable: false },
    { title: t('ai.toolStatus'), key: 'status', sortable: false },
    { title: t('ai.toolInput'), key: 'input_json', sortable: false },
    { title: t('ai.toolOutput'), key: 'output_json', sortable: false },
    { title: t('ai.createdAt'), key: 'created_at', sortable: false },
  ])

  const promptMemoryHeaders = computed(() => [
    { title: t('ai.memoryLayer'), key: 'memory_layer', sortable: false },
    { title: t('ai.memoryKind'), key: 'memory_kind', sortable: false },
    { title: t('ai.memoryContent'), key: 'content', sortable: false },
    { title: t('ai.memoryConfidence'), key: 'confidence', sortable: false },
    { title: t('ai.memorySalience'), key: 'salience', sortable: false },
  ])

  const futureTaskHeaders = computed(() => [
    { title: t('ai.futureTaskId'), key: 'task_id', sortable: false },
    { title: t('ai.futureTaskTitle'), key: 'title', sortable: false },
    { title: t('ai.futureTaskDescription'), key: 'description', sortable: false },
    { title: t('ai.futureTaskTriggerAt'), key: 'trigger_at', sortable: false },
    { title: t('ai.futureTaskStatus'), key: 'status', sortable: false },
    { title: t('ai.createdAt'), key: 'created_at', sortable: false },
    { title: t('common.actions'), key: 'actions', sortable: false, align: 'end' as const },
  ])
</script>

<style scoped>
.ai-debug-layout {
  display: grid;
  grid-template-columns: minmax(176px, 220px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.ai-debug-nav {
  position: sticky;
  top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding: 6px;
  border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-surface-container-low), 0.8);
}

.ai-debug-nav__item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
  min-height: 38px;
  padding: 0 10px;
  border: 0;
  border-radius: var(--shape-small);
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.72);
  font: inherit;
  font-weight: 650;
  text-align: left;
  transition:
    background-color var(--motion-fast) var(--motion-ease),
    color var(--motion-fast) var(--motion-ease),
    box-shadow var(--motion-fast) var(--motion-ease);
}

.ai-debug-nav__item:hover {
  color: rgb(var(--v-theme-on-surface));
  background: rgba(var(--v-theme-primary), 0.06);
}

.ai-debug-nav__item:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.ai-debug-nav__item--active {
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.18);
}

.ai-debug-content {
  min-width: 0;
}

@media (max-width: 640px) {
  .ai-debug-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .ai-debug-nav {
    position: static;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .ai-debug-nav__item {
    justify-content: center;
    text-align: center;
  }
}
</style>
