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

    <div class="page-summary-grid mb-4">
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('ai.skills') }}</div>
        <div class="summary-card__value">{{ tools.length }}</div>
      </v-sheet>
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('ai.modelProfiles') }}</div>
        <div class="summary-card__value">{{ modelProfiles.length }}</div>
      </v-sheet>
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('ai.personas') }}</div>
        <div class="summary-card__value">{{ personas.length }}</div>
      </v-sheet>
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('ai.providers') }}</div>
        <div class="summary-card__value">{{ providers.length }}</div>
      </v-sheet>
    </div>

    <v-card class="page-panel">
      <v-tabs v-model="tab" color="primary">
        <v-tab value="workbench">{{ t('ai.workbenchTab') }}</v-tab>
        <v-tab value="tools">{{ t('ai.toolsTab') }}</v-tab>
        <v-tab value="personas">{{ t('ai.personasTab') }}</v-tab>
        <v-tab value="memory">{{ t('ai.memoryTab') }}</v-tab>
        <v-tab value="relationship">{{ t('ai.relationshipTab') }}</v-tab>
        <v-tab value="models">{{ t('ai.modelsTab') }}</v-tab>
      </v-tabs>

      <v-window v-model="tab">
        <v-window-item value="workbench">
          <v-card-text class="d-flex flex-column ga-5">
            <div class="ai-binding-form">
              <v-text-field
                v-model.number="workbenchForm.limit"
                density="comfortable"
                hide-details
                :label="t('ai.workbenchConversationLimit')"
                min="1"
                type="number"
              />
              <v-text-field
                v-model.number="workbenchForm.turnLimit"
                density="comfortable"
                hide-details
                :label="t('ai.workbenchTurnLimit')"
                min="1"
                type="number"
              />
            </div>

            <div class="d-flex justify-end">
              <v-btn color="primary" :loading="loadingWorkbench" @click="loadWorkbenchData">
                {{ t('ai.loadWorkbench') }}
              </v-btn>
            </div>

            <v-row>
              <v-col cols="12" lg="5">
                <v-data-table
                  class="page-table"
                  density="compact"
                  :headers="conversationHeaders"
                  :items="conversations"
                  :loading="loadingWorkbench"
                >
                  <template #item.conversation_id="{ item }">
                    <v-btn
                      color="primary"
                      size="small"
                      variant="text"
                      @click="loadConversationDetails(item.conversation_id)"
                    >
                      {{ item.conversation_id.slice(0, 16) }}...
                    </v-btn>
                  </template>
                </v-data-table>
              </v-col>

              <v-col cols="12" lg="7">
                <v-sheet class="surface-gradient-card pa-4 mb-4" rounded="lg">
                  <div class="text-subtitle-2 mb-2">{{ t('ai.workbenchSelectedConversation') }}</div>
                  <div v-if="selectedConversation" class="d-flex flex-column ga-2 text-body-2">
                    <div>{{ t('ai.conversationId') }}: {{ selectedConversation.conversation_id }}</div>
                    <div>{{ t('ai.scopeType') }}: {{ selectedConversation.scope_type }}</div>
                    <div>{{ t('ai.scopeId') }}: {{ selectedConversation.scope_id }}</div>
                    <div>{{ t('ai.conversationSummary') }}: {{ selectedConversation.short_summary || t('common.none') }}</div>
                    <div>{{ t('ai.lastActiveAt') }}: {{ selectedConversation.last_active_at }}</div>
                  </div>
                  <div v-else class="text-body-2 text-medium-emphasis">
                    {{ t('ai.noConversationSelected') }}
                  </div>
                </v-sheet>

                <v-sheet class="surface-gradient-card pa-4 mb-4" rounded="lg">
                  <div class="text-subtitle-2 mb-2">{{ t('ai.traceIds') }}</div>
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
                  <div v-else class="text-body-2 text-medium-emphasis">
                    {{ t('ai.noTraceIds') }}
                  </div>
                </v-sheet>

                <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                  <div class="text-subtitle-2 mb-2">{{ t('ai.toolExecutionSummary') }}</div>
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
              </v-col>
            </v-row>

            <v-sheet class="surface-gradient-card pa-4" rounded="lg">
              <div class="text-subtitle-2 mb-2">{{ t('ai.promptPreviewTitle') }}</div>
              <div v-if="promptPreview" class="d-flex flex-column ga-3 text-body-2">
                <div>{{ t('ai.latestUserMessage') }}: {{ promptPreview.latest_user_message || t('common.none') }}</div>
                <div>{{ t('ai.modelName') }}: {{ promptPreview.model_name || t('common.none') }}</div>
                <div>{{ t('ai.personaId') }}: {{ promptPreview.persona_id || t('common.none') }}</div>
                <div>{{ t('ai.relationshipStateTitle') }}: {{ promptPreview.relationship_context || t('common.none') }}</div>
                <div>{{ t('ai.toolPolicyTitle') }}: {{ promptPreview.tool_policy || t('common.none') }}</div>
                <div>{{ t('ai.memoryHits') }}: {{ promptPreview.memories.length }}</div>
                <div>{{ t('ai.toolResultsTitle') }}: {{ promptPreview.tool_results.length }}</div>
                <pre class="ai-prompt-preview">{{ promptPreview.rendered_prompt }}</pre>
              </div>
              <div v-else class="text-body-2 text-medium-emphasis">
                {{ t('ai.noPromptPreview') }}
              </div>
            </v-sheet>

            <v-data-table
              class="page-table"
              density="compact"
              :headers="promptMemoryHeaders"
              :items="promptPreview?.memories || []"
            />

            <v-data-table
              class="page-table"
              density="compact"
              :headers="turnHeaders"
              :items="turns"
              :loading="loadingTurns"
            >
              <template #item.content_text="{ value }">
                <span class="ai-turn-content">{{ value }}</span>
              </template>
              <template #item.raw_payload="{ item }">
                <span class="text-medium-emphasis">{{ summarizeRawPayload(item.raw_payload) }}</span>
              </template>
            </v-data-table>

            <v-data-table
              class="page-table"
              density="compact"
              :headers="toolExecutionHeaders"
              :items="toolExecutions"
              :loading="loadingTurns"
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
          </v-card-text>
        </v-window-item>

        <v-window-item value="tools">
          <v-card-text class="d-flex flex-column ga-5">
            <v-row>
              <v-col cols="12" xl="7">
                <div class="d-flex flex-column ga-4">
                  <v-data-table
                    class="page-table"
                    density="compact"
                    :headers="skillHeaders"
                    :items="tools"
                  >
                    <template #item.read_only="{ value }">
                      <v-chip :color="value ? 'success' : 'default'" size="x-small" variant="tonal">
                        {{ value ? t('ai.enabled') : t('ai.disabled') }}
                      </v-chip>
                    </template>
                    <template #item.risk_level="{ value }">
                      <v-chip color="primary" size="x-small" variant="tonal">
                        {{ value }}
                      </v-chip>
                    </template>
                  </v-data-table>

                  <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                    <div class="text-subtitle-2 mb-2">{{ t('ai.capabilityRegistry') }}</div>
                    <div class="d-flex flex-wrap ga-2">
                      <v-chip
                        v-for="item in capabilities"
                        :key="item.capability_name"
                        color="primary"
                        size="small"
                        variant="tonal"
                      >
                        {{ item.capability_name }}
                      </v-chip>
                    </div>
                  </v-sheet>
                </div>
              </v-col>

              <v-col cols="12" xl="5">
                <div class="d-flex flex-column ga-4">
                  <v-expansion-panels variant="accordion">
                    <v-expansion-panel>
                      <v-expansion-panel-title>
                        {{ t('ai.advancedDebugTitle') }}
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <div class="text-body-2 text-medium-emphasis mb-4">
                          {{ t('ai.advancedDebugHint') }}
                        </div>

                        <div class="ai-binding-form mb-4">
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

                        <div class="d-flex ga-3 justify-end mb-4">
                          <v-btn
                            v-if="editingBindingId"
                            :loading="saving"
                            variant="text"
                            @click="resetBindingForm"
                          >
                            {{ t('common.cancel') }}
                          </v-btn>
                          <v-btn color="primary" :loading="saving" @click="submitBinding(() => loadData())">
                            {{ editingBindingId ? t('ai.updateBinding') : t('ai.createBinding') }}
                          </v-btn>
                        </div>

                        <v-data-table
                          class="page-table mb-4"
                          density="compact"
                          :headers="bindingHeaders"
                          :items="bindings"
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
                                @click="removeBinding(item.binding_id, () => loadData())"
                              />
                            </div>
                          </template>
                        </v-data-table>

                        <div class="ai-binding-form mb-4">
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

                        <div class="d-flex ga-3 justify-end mb-4">
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

                        <v-sheet class="surface-gradient-card pa-4 mb-4" rounded="lg">
                          <div class="text-subtitle-2 mb-2">{{ t('ai.policyPreviewResult') }}</div>
                          <div v-if="policyPreview" class="d-flex flex-column ga-2 text-body-2">
                            <div>{{ t('ai.executionEnabled') }}: {{ policyPreview.execution_enabled ? t('ai.enabled') : t('ai.disabled') }}</div>
                            <div>{{ t('ai.allowCapabilityBridge') }}: {{ policyPreview.allow_capability_bridge ? t('ai.enabled') : t('ai.disabled') }}</div>
                            <div>{{ t('ai.allowedTools') }}: {{ policyPreview.allowed_tool_names?.join(', ') || t('common.none') }}</div>
                          </div>
                          <div v-else class="text-body-2 text-medium-emphasis">
                            {{ t('ai.noPreviewYet') }}
                          </div>
                        </v-sheet>

                        <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                          <div class="text-subtitle-2 mb-2">{{ t('ai.capabilityPreviewResult') }}</div>
                          <div v-if="capabilityPreview" class="d-flex flex-column ga-2 text-body-2">
                            <div>{{ t('ai.capabilityName') }}: {{ capabilityPreview.capability_name }}</div>
                            <div>{{ t('ai.registered') }}: {{ capabilityPreview.registered ? t('ai.enabled') : t('ai.disabled') }}</div>
                            <div>{{ t('ai.allowed') }}: {{ capabilityPreview.allowed ? t('ai.enabled') : t('ai.disabled') }}</div>
                            <div>{{ t('ai.reason') }}: {{ capabilityPreview.reason }}</div>
                          </div>
                          <div v-else class="text-body-2 text-medium-emphasis">
                            {{ t('ai.noPreviewYet') }}
                          </div>
                        </v-sheet>

                        <v-sheet class="surface-gradient-card pa-4 mt-4" rounded="lg">
                          <div class="text-subtitle-2 mb-2">{{ t('ai.intentPreviewResult') }}</div>
                          <v-data-table
                            class="page-table"
                            density="compact"
                            :headers="intentPreviewHeaders"
                            :items="intentPreview"
                          />
                        </v-sheet>
                      </v-expansion-panel-text>
                    </v-expansion-panel>
                  </v-expansion-panels>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-window-item>

        <v-window-item value="personas">
          <v-card-text class="d-flex flex-column ga-4">
            <v-data-table
              class="page-table"
              density="compact"
              :headers="personaHeaders"
              :items="personas"
            >
              <template #item.enabled="{ value }">
                <v-chip :color="value ? 'success' : 'default'" size="x-small" variant="tonal">
                  {{ value ? t('ai.enabled') : t('ai.disabled') }}
                </v-chip>
              </template>
            </v-data-table>

            <v-data-table
              class="page-table"
              density="compact"
              :headers="personaBindingHeaders"
              :items="personaBindings"
            />
          </v-card-text>
        </v-window-item>

        <v-window-item value="memory">
          <v-card-text class="d-flex flex-column ga-4">
            <div class="ai-binding-form">
              <v-select
                v-model="memoryForm.subject_type"
                density="comfortable"
                hide-details
                :items="memorySubjectOptions"
                :label="t('ai.memorySubjectType')"
              />
              <v-text-field
                v-model.trim="memoryForm.subject_id"
                density="comfortable"
                hide-details
                :label="t('ai.memorySubjectId')"
              />
              <v-text-field
                v-model.trim="memoryForm.query"
                density="comfortable"
                hide-details
                :label="t('ai.memoryQuery')"
              />
              <v-text-field
                v-model.number="memoryForm.limit"
                density="comfortable"
                hide-details
                :label="t('ai.memoryLimit')"
                type="number"
              />
            </div>

            <div class="d-flex justify-end">
              <v-btn color="primary" :loading="loadingMemories" @click="loadMemories">
                {{ t('ai.loadMemories') }}
              </v-btn>
            </div>

            <v-data-table
              class="page-table"
              density="compact"
              :headers="memoryHeaders"
              :items="memories"
            />
          </v-card-text>
        </v-window-item>

        <v-window-item value="relationship">
          <v-card-text class="d-flex flex-column ga-4">
            <div class="ai-binding-form">
              <v-text-field
                v-model.trim="relationshipForm.platform"
                density="comfortable"
                hide-details
                :label="t('ai.relationshipPlatform')"
              />
              <v-text-field
                v-model.trim="relationshipForm.user_id"
                density="comfortable"
                hide-details
                :label="t('ai.relationshipUserId')"
              />
              <v-text-field
                v-model.trim="relationshipForm.group_id"
                density="comfortable"
                hide-details
                :label="t('ai.relationshipGroupId')"
              />
              <v-text-field
                v-model.number="relationshipForm.score"
                density="comfortable"
                hide-details
                :label="t('ai.relationshipScore')"
                max="1"
                min="-1"
                step="0.1"
                type="number"
              />
            </div>

            <div class="d-flex ga-3 justify-end">
              <v-btn :loading="loadingRelationship" variant="tonal" @click="loadRelationship">
                {{ t('ai.loadRelationship') }}
              </v-btn>
              <v-btn color="primary" :loading="savingRelationship" @click="saveRelationship">
                {{ t('ai.saveRelationship') }}
              </v-btn>
            </div>

            <v-sheet class="surface-gradient-card pa-4" rounded="lg">
              <div class="text-subtitle-2 mb-2">{{ t('ai.relationshipStateTitle') }}</div>
              <div v-if="relationship" class="d-flex flex-column ga-2 text-body-2">
                <div>{{ t('ai.relationshipScore') }}: {{ relationship.score }}</div>
                <div>{{ t('ai.relationshipMoodTags') }}: {{ relationship.mood_tags.join(', ') || t('common.none') }}</div>
                <div>{{ t('ai.relationshipLastEventAt') }}: {{ relationship.last_event_at }}</div>
              </div>
              <div v-else class="text-body-2 text-medium-emphasis">
                {{ t('ai.noRelationshipLoaded') }}
              </div>
            </v-sheet>
          </v-card-text>
        </v-window-item>

        <v-window-item value="models">
          <v-card-text class="d-flex flex-column ga-4">
            <v-data-table
              class="page-table"
              density="compact"
              :headers="providerHeaders"
              :items="providers"
            >
              <template #item.enabled="{ value }">
                <v-chip :color="value ? 'success' : 'default'" size="x-small" variant="tonal">
                  {{ value ? t('ai.enabled') : t('ai.disabled') }}
                </v-chip>
              </template>
            </v-data-table>

            <v-data-table
              class="page-table"
              density="compact"
              :headers="modelProfileHeaders"
              :items="modelProfiles"
            >
              <template #item.enabled="{ value }">
                <v-chip :color="value ? 'success' : 'default'" size="x-small" variant="tonal">
                  {{ value ? t('ai.enabled') : t('ai.disabled') }}
                </v-chip>
              </template>
            </v-data-table>

            <v-data-table
              class="page-table"
              density="compact"
              :headers="modelBindingHeaders"
              :items="modelBindings"
            />
          </v-card-text>
        </v-window-item>
      </v-window>
    </v-card>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { getErrorMessage } from '@/api/client'
  import { useAIMemoryTab } from '@/composables/useAIMemoryTab'
  import { useAIModelsTab } from '@/composables/useAIModelsTab'
  import { useAIPersonasTab } from '@/composables/useAIPersonasTab'
  import { useAIRelationshipTab } from '@/composables/useAIRelationshipTab'
  import { useAIToolsTab } from '@/composables/useAIToolsTab'
  import { useAIWorkbenchTab } from '@/composables/useAIWorkbenchTab'

  const { t } = useI18n()

  const loading = ref(false)
  const errorMessage = ref('')
  const tab = ref('workbench')

  const {
    conversations,
    loadConversationDetails,
    loadWorkbenchData,
    loadingTurns,
    loadingWorkbench,
    promptPreview,
    selectedConversation,
    summarizeJsonText,
    summarizeRawPayload,
    toolExecutions,
    toolExecutionStats,
    traceIds,
    turns,
    workbenchForm,
  } = useAIWorkbenchTab(t)

  const {
    bindingForm,
    bindings,
    capabilities,
    capabilityPreview,
    capabilityPreviewName,
    editBinding,
    editingBindingId,
    intentPreview,
    intentPreviewForm,
    loadToolsData,
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
    tools,
  } = useAIToolsTab(t)

  const {
    loadPersonasData,
    personaBindings,
    personas,
  } = useAIPersonasTab()

  const {
    loadModelsData,
    modelBindings,
    modelProfiles,
    providers,
  } = useAIModelsTab()

  const {
    loadMemories,
    loadingMemories,
    memories,
    memoryForm,
  } = useAIMemoryTab(t)

  const {
    loadRelationship,
    loadingRelationship,
    relationship,
    relationshipForm,
    saveRelationship,
    savingRelationship,
  } = useAIRelationshipTab(t)

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

  const bindingHeaders = computed(() => [
    { title: t('ai.scopeType'), key: 'scope_type', sortable: false },
    { title: t('ai.scopeId'), key: 'scope_id', sortable: false },
    { title: t('ai.allowReadOnlyTools'), key: 'allow_read_only_tools', sortable: false },
    { title: t('ai.capabilityMode'), key: 'capability_mode', sortable: false },
    { title: 'Actions', key: 'actions', sortable: false, align: 'end' as const },
  ])

  const skillHeaders = computed(() => [
    { title: t('ai.skillName'), key: 'name', sortable: false },
    { title: t('ai.skillDescription'), key: 'description', sortable: false },
    { title: t('ai.skillRiskLevel'), key: 'risk_level', sortable: false },
    { title: t('ai.skillReadOnly'), key: 'read_only', sortable: false },
  ])

  const intentPreviewHeaders = computed(() => [
    { title: t('ai.toolName'), key: 'tool_name', sortable: false },
    { title: t('ai.intentKind'), key: 'kind', sortable: false },
    { title: t('ai.reason'), key: 'reason', sortable: false },
  ])

  const conversationHeaders = computed(() => [
    { title: t('ai.conversationId'), key: 'conversation_id', sortable: false },
    { title: t('ai.scopeType'), key: 'scope_type', sortable: false },
    { title: t('ai.scopeId'), key: 'scope_id', sortable: false },
    { title: t('ai.conversationSummary'), key: 'short_summary', sortable: false },
    { title: t('ai.lastActiveAt'), key: 'last_active_at', sortable: false },
  ])

  const turnHeaders = computed(() => [
    { title: t('ai.turnSender'), key: 'sender_type', sortable: false },
    { title: t('ai.turnContent'), key: 'content_text', sortable: false },
    { title: t('ai.traceId'), key: 'trace_id', sortable: false },
    { title: t('ai.modelName'), key: 'model_name', sortable: false },
    { title: t('ai.turnRawPayload'), key: 'raw_payload', sortable: false },
  ])

  const toolExecutionHeaders = computed(() => [
    { title: t('ai.toolName'), key: 'tool_name', sortable: false },
    { title: t('ai.toolStatus'), key: 'status', sortable: false },
    { title: t('ai.toolInput'), key: 'input_json', sortable: false },
    { title: t('ai.toolOutput'), key: 'output_json', sortable: false },
    { title: t('ai.createdAt'), key: 'created_at', sortable: false },
  ])

  const promptMemoryHeaders = computed(() => [
    { title: t('ai.memoryType'), key: 'memory_type', sortable: false },
    { title: t('ai.memoryContent'), key: 'content', sortable: false },
    { title: t('ai.memoryConfidence'), key: 'confidence', sortable: false },
    { title: t('ai.memorySalience'), key: 'salience', sortable: false },
  ])

  const personaHeaders = computed(() => [
    { title: t('ai.personaName'), key: 'name', sortable: false },
    { title: t('ai.personaDescription'), key: 'description', sortable: false },
    { title: t('ai.personaEnabled'), key: 'enabled', sortable: false },
  ])

  const personaBindingHeaders = computed(() => [
    { title: t('ai.scopeType'), key: 'scope_type', sortable: false },
    { title: t('ai.scopeId'), key: 'scope_id', sortable: false },
    { title: t('ai.personaId'), key: 'persona_id', sortable: false },
  ])

  const memorySubjectOptions = computed(() => [
    { title: t('ai.scopeUser'), value: 'user' },
    { title: t('ai.scopeConversation'), value: 'conversation' },
  ])

  const memoryHeaders = computed(() => [
    { title: t('ai.memoryType'), key: 'memory_type', sortable: false },
    { title: t('ai.memoryContent'), key: 'content', sortable: false },
    { title: t('ai.memorySubjectId'), key: 'subject_id', sortable: false },
  ])

  const providerHeaders = computed(() => [
    { title: t('ai.providerName'), key: 'name', sortable: false },
    { title: t('ai.providerType'), key: 'provider_type', sortable: false },
    { title: t('ai.providerDefaultModel'), key: 'default_model', sortable: false },
    { title: t('ai.providerEnabled'), key: 'enabled', sortable: false },
  ])

  const modelProfileHeaders = computed(() => [
    { title: t('ai.modelProfileName'), key: 'name', sortable: false },
    { title: t('ai.modelName'), key: 'model_name', sortable: false },
    { title: t('ai.modelTaskClass'), key: 'task_class', sortable: false },
    { title: t('ai.providerId'), key: 'provider_id', sortable: false },
    { title: t('ai.modelEnabled'), key: 'enabled', sortable: false },
  ])

  const modelBindingHeaders = computed(() => [
    { title: t('ai.scopeType'), key: 'scope_type', sortable: false },
    { title: t('ai.scopeId'), key: 'scope_id', sortable: false },
    { title: t('ai.modelProfileId'), key: 'profile_id', sortable: false },
  ])

  async function loadData () {
    loading.value = true
    errorMessage.value = ''
    try {
      await Promise.all([
        loadWorkbenchData(),
        loadToolsData(),
        loadPersonasData(),
        loadModelsData(),
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
.ai-binding-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 960px) {
  .ai-binding-form {
    grid-template-columns: 1fr;
  }
}
</style>
