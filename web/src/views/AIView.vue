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
        <v-tab value="providers">{{ t('ai.providersTab') }}</v-tab>
        <v-tab value="personas">{{ t('ai.personasTab') }}</v-tab>
        <v-tab value="memories">{{ t('ai.memoryTab') }}</v-tab>
        <v-tab value="relationships">{{ t('ai.relationshipTab') }}</v-tab>
        <v-tab value="skills">{{ t('ai.skillsTab') }}</v-tab>
        <v-tab value="debug">{{ t('ai.debugTab') }}</v-tab>
      </v-tabs>

      <template v-if="topTab === 'providers'">
        <v-card-text>
          <v-row>
            <v-col cols="12" lg="4">
              <div class="d-flex justify-end mb-3">
                <v-btn color="primary" variant="tonal" @click="startCreateProvider">
                  {{ t('ai.createProvider') }}
                </v-btn>
              </div>
              <v-sheet class="surface-gradient-card pa-2" rounded="lg">
                <template v-if="providers.length > 0">
                  <v-list class="bg-transparent" density="comfortable" lines="two">
                    <v-list-item
                      v-for="item in providers"
                      :key="item.provider_id"
                      :active="item.provider_id === providerForm.provider_id"
                      rounded="lg"
                      @click="selectProvider(item)"
                    >
                      <v-list-item-title>{{ item.name }}</v-list-item-title>
                      <v-list-item-subtitle>
                        {{ providerTypeLabel(item.provider_type) }} · {{ item.default_model || t('common.none') }}
                      </v-list-item-subtitle>
                      <template #append>
                        <v-chip :color="item.enabled ? 'success' : 'default'" size="small" variant="tonal">
                          {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
                        </v-chip>
                      </template>
                    </v-list-item>
                  </v-list>
                </template>
                <div v-else class="pa-4">
                  <div class="empty-state-text">{{ t('ai.noProviders') }}</div>
                  <div class="empty-state-hint mt-2">{{ t('ai.noProvidersHint') }}</div>
                </div>
              </v-sheet>
            </v-col>

            <v-col cols="12" lg="8">
              <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                <div class="d-flex flex-wrap ga-2 mb-4">
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ isCreatingProvider ? t('ai.creatingProvider') : t('ai.editingProvider') }}
                  </v-chip>
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ t('ai.providerDefaultModel') }}: {{ providerForm.default_model || t('common.none') }}
                  </v-chip>
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ t('ai.modelProfiles') }}: {{ selectedProviderProfileCount }}
                  </v-chip>
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ t('ai.scopeBindings') }}: {{ selectedProviderBindingCount }}
                  </v-chip>
                </div>

                <div class="ai-binding-form">
                  <v-text-field
                    v-model.trim="providerForm.name"
                    density="comfortable"
                    :disabled="savingProvider"
                    :error-messages="displayedProviderErrors.name ? [displayedProviderErrors.name] : []"
                    :label="t('ai.providerName')"
                    @blur="touchProviderField('name')"
                  />
                  <v-select
                    v-model="providerForm.provider_type"
                    density="comfortable"
                    :disabled="savingProvider"
                    :error-messages="displayedProviderErrors.provider_type ? [displayedProviderErrors.provider_type] : []"
                    :items="providerTypeOptions"
                    :label="t('ai.providerType')"
                    @blur="touchProviderField('provider_type')"
                  />
                  <v-text-field
                    v-model.trim="providerForm.default_model"
                    density="comfortable"
                    :disabled="savingProvider"
                    hide-details
                    :label="t('ai.providerDefaultModel')"
                  />
                  <v-text-field
                    v-model.trim="providerForm.api_key_env_name"
                    density="comfortable"
                    :disabled="savingProvider"
                    hide-details
                    :label="t('ai.providerApiKeyEnv')"
                  />
                </div>

                <v-text-field
                  v-model.trim="providerForm.api_base"
                  class="mt-3"
                  density="comfortable"
                  :disabled="savingProvider"
                  hide-details
                  :label="t('ai.providerApiBase')"
                />

                <v-switch
                  v-model="providerForm.enabled"
                  class="mt-3"
                  color="primary"
                  density="comfortable"
                  :disabled="savingProvider"
                  hide-details
                  :label="t('ai.providerEnabled')"
                />

                <div class="d-flex justify-end mt-4">
                  <v-btn color="primary" :disabled="!canSaveProvider" :loading="savingProvider" @click="saveProvider">
                    {{ t('common.save') }}
                  </v-btn>
                </div>
              </v-sheet>
            </v-col>
          </v-row>
        </v-card-text>
      </template>

      <template v-else-if="topTab === 'personas'">
        <v-card-text>
          <v-row>
            <v-col cols="12" lg="4">
              <div class="d-flex justify-end mb-3">
                <v-btn color="primary" variant="tonal" @click="startCreatePersona">
                  {{ t('ai.createPersona') }}
                </v-btn>
              </div>
              <v-sheet class="surface-gradient-card pa-2" rounded="lg">
                <template v-if="personas.length > 0">
                  <v-list class="bg-transparent" density="comfortable" lines="two">
                    <v-list-item
                      v-for="item in personas"
                      :key="item.persona_id"
                      :active="item.persona_id === personaForm.persona_id"
                      rounded="lg"
                      @click="selectPersona(item)"
                    >
                      <v-list-item-title>{{ item.name }}</v-list-item-title>
                      <v-list-item-subtitle>{{ item.description || t('common.none') }}</v-list-item-subtitle>
                      <template #append>
                        <v-chip :color="item.enabled ? 'success' : 'default'" size="small" variant="tonal">
                          {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
                        </v-chip>
                      </template>
                    </v-list-item>
                  </v-list>
                </template>
                <div v-else class="pa-4">
                  <div class="empty-state-text">{{ t('ai.noPersonas') }}</div>
                  <div class="empty-state-hint mt-2">{{ t('ai.noPersonasHint') }}</div>
                </div>
              </v-sheet>
            </v-col>

            <v-col cols="12" lg="8">
              <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                <div class="d-flex flex-wrap ga-2 mb-4">
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ isCreatingPersona ? t('ai.creatingPersona') : t('ai.editingPersona') }}
                  </v-chip>
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ t('ai.scopeBindings') }}: {{ selectedPersonaBindingCount }}
                  </v-chip>
                </div>

                <v-text-field
                  v-model.trim="personaForm.name"
                  density="comfortable"
                  :disabled="savingPersona"
                  :error-messages="displayedPersonaErrors.name ? [displayedPersonaErrors.name] : []"
                  :label="t('ai.personaName')"
                  @blur="touchPersonaField('name')"
                />
                <v-text-field
                  v-model.trim="personaForm.description"
                  class="mt-3"
                  density="comfortable"
                  :disabled="savingPersona"
                  :error-messages="displayedPersonaErrors.description ? [displayedPersonaErrors.description] : []"
                  :label="t('ai.personaDescription')"
                  @blur="touchPersonaField('description')"
                />
                <v-textarea
                  v-model.trim="personaForm.system_prompt"
                  auto-grow
                  class="mt-3"
                  density="comfortable"
                  :disabled="savingPersona"
                  :error-messages="displayedPersonaErrors.system_prompt ? [displayedPersonaErrors.system_prompt] : []"
                  :label="t('ai.personaSystemPrompt')"
                  rows="5"
                  @blur="touchPersonaField('system_prompt')"
                />
                <v-textarea
                  v-model.trim="personaForm.style_prompt"
                  auto-grow
                  class="mt-3"
                  density="comfortable"
                  :disabled="savingPersona"
                  hide-details
                  :label="t('ai.personaStylePrompt')"
                  rows="4"
                />
                <v-switch
                  v-model="personaForm.enabled"
                  class="mt-3"
                  color="primary"
                  density="comfortable"
                  :disabled="savingPersona"
                  hide-details
                  :label="t('ai.personaEnabled')"
                />
                <div class="d-flex justify-end mt-4">
                  <v-btn color="primary" :disabled="!canSavePersona" :loading="savingPersona" @click="savePersona">
                    {{ t('common.save') }}
                  </v-btn>
                </div>
              </v-sheet>
            </v-col>
          </v-row>
        </v-card-text>
      </template>

      <template v-else-if="topTab === 'memories'">
        <v-card-text>
          <v-row>
            <v-col cols="12" lg="4">
              <v-sheet class="surface-gradient-card pa-2" rounded="lg">
                <div class="d-flex align-center justify-space-between px-2 py-2">
                  <div class="text-body-2 text-medium-emphasis">{{ t('ai.recentTargets') }}</div>
                  <v-btn
                    icon="mdi-refresh"
                    :loading="loadingRecentTargets"
                    size="small"
                    variant="text"
                    @click="loadRecentTargets"
                  />
                </div>
                <template v-if="recentTargets.length > 0">
                  <v-list class="bg-transparent" density="comfortable" lines="two">
                    <v-list-item
                      v-for="item in recentTargets"
                      :key="`${item.subject_type}:${item.subject_id}`"
                      :active="selectedRecentTargetId === `${item.subject_type}:${item.subject_id}`"
                      rounded="lg"
                      @click="selectRecentTarget(item)"
                    >
                      <v-list-item-title>{{ item.title }}</v-list-item-title>
                      <v-list-item-subtitle>{{ item.subtitle || item.subject_id }}</v-list-item-subtitle>
                      <template #append>
                        <v-chip color="primary" size="small" variant="tonal">
                          {{ item.subject_type === 'conversation' ? t('ai.scopeConversation') : t('ai.scopeUser') }}
                        </v-chip>
                      </template>
                    </v-list-item>
                  </v-list>
                </template>
                <div v-else class="pa-4">
                  <div class="empty-state-text">{{ t('ai.noRecentTargets') }}</div>
                  <div class="empty-state-hint mt-2">{{ t('ai.noRecentTargetsHint') }}</div>
                </div>
              </v-sheet>
            </v-col>

            <v-col class="d-flex flex-column ga-4" cols="12" lg="8">
              <v-expansion-panels variant="accordion">
                <v-expansion-panel>
                  <v-expansion-panel-title>{{ t('ai.advancedInput') }}</v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <div class="ai-binding-form ai-memory-toolbar pt-2">
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
                      <v-select
                        v-model="memoryForm.limit"
                        density="comfortable"
                        hide-details
                        :items="memoryLimitOptions"
                        :label="t('ai.memoryLimit')"
                      />
                    </div>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>

              <div class="d-flex flex-wrap ga-2 justify-space-between align-center">
                <div class="d-flex flex-wrap ga-2">
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ t('ai.memoryTarget') }}: {{ memoryTargetLabel }}
                  </v-chip>
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ t('ai.memoryCount') }}: {{ memories.length }}
                  </v-chip>
                  <v-chip
                    v-for="item in memoryTypeBreakdown"
                    :key="item.memoryType"
                    color="primary"
                    size="small"
                    variant="tonal"
                  >
                    {{ item.memoryType }}: {{ item.count }}
                  </v-chip>
                </div>

                <v-btn
                  color="primary"
                  :disabled="!canLoadMemories"
                  :loading="loadingMemories"
                  @click="loadMemories"
                >
                  {{ t('ai.viewMemories') }}
                </v-btn>
              </div>

              <div v-if="memories.length > 0" class="memory-card-list">
                <v-sheet
                  v-for="item in memories"
                  :key="item.memory_id"
                  class="surface-gradient-card pa-4"
                  rounded="lg"
                >
                  <div class="d-flex flex-wrap justify-space-between ga-3">
                    <div class="d-flex flex-wrap ga-2">
                      <v-chip color="primary" size="small" variant="tonal">
                        {{ item.memory_type }}
                      </v-chip>
                      <v-chip color="primary" size="small" variant="tonal">
                        {{ t('ai.memoryConfidence') }}: {{ formatMemoryScore(item.confidence) }}
                      </v-chip>
                      <v-chip color="primary" size="small" variant="tonal">
                        {{ t('ai.memorySalience') }}: {{ formatMemoryScore(item.salience) }}
                      </v-chip>
                    </div>
                    <div class="text-caption text-medium-emphasis">
                      {{ t('ai.memoryCreatedAt') }}: {{ item.created_at }}
                    </div>
                  </div>

                  <div class="text-body-1 mt-3 memory-content-text">{{ item.content }}</div>

                  <div class="d-flex flex-wrap ga-4 mt-3 text-caption text-medium-emphasis">
                    <span>{{ t('ai.memoryLastRecalledAt') }}: {{ item.last_recalled_at || t('common.none') }}</span>
                    <span>{{ t('ai.memorySourceTurn') }}: {{ formatMemorySourceTurn(item.source_turn_id) }}</span>
                  </div>
                </v-sheet>
              </div>

              <v-sheet v-else class="surface-gradient-card pa-4" rounded="lg">
                <div class="empty-state-text mb-3">
                  {{ canLoadMemories ? t('ai.noMemories') : t('ai.selectMemoryTarget') }}
                </div>
                <div class="d-flex flex-wrap ga-3">
                  <v-btn color="primary" variant="tonal" @click="openDebugConversations()">
                    {{ t('ai.goToDebug') }}
                  </v-btn>
                  <v-btn variant="text" @click="openChatView()">
                    {{ t('ai.goToChatView') }}
                  </v-btn>
                </div>
              </v-sheet>
            </v-col>
          </v-row>
        </v-card-text>
      </template>

      <template v-else-if="topTab === 'relationships'">
        <v-card-text>
          <v-row>
            <v-col cols="12" lg="4">
              <v-sheet class="surface-gradient-card pa-2" rounded="lg">
                <div class="d-flex align-center justify-space-between px-2 py-2">
                  <div class="text-body-2 text-medium-emphasis">{{ t('ai.recentTargets') }}</div>
                  <v-btn
                    icon="mdi-refresh"
                    :loading="loadingRecentTargets || loadingSelectedRelationship"
                    size="small"
                    variant="text"
                    @click="loadRecentTargets"
                  />
                </div>
                <template v-if="recentUserTargets.length > 0">
                  <v-list class="bg-transparent" density="comfortable" lines="two">
                    <v-list-item
                      v-for="item in recentUserTargets"
                      :key="`${item.subject_type}:${item.subject_id}`"
                      rounded="lg"
                      @click="loadRelationshipForTarget(item)"
                    >
                      <v-list-item-title>{{ item.title }}</v-list-item-title>
                      <v-list-item-subtitle>{{ item.subtitle || item.subject_id }}</v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </template>
                <div v-else class="pa-4">
                  <div class="empty-state-text">{{ t('ai.noRecentTargets') }}</div>
                  <div class="empty-state-hint mt-2">{{ t('ai.noRecentTargetsHint') }}</div>
                </div>
              </v-sheet>
            </v-col>

            <v-col cols="12" lg="8">
              <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                <div v-if="relationship" class="d-flex flex-column ga-4">
                  <div class="d-flex flex-wrap ga-2">
                    <v-chip color="primary" size="small" variant="tonal">
                      {{ t('ai.relationshipTarget') }}: {{ relationshipSelectionLabel }}
                    </v-chip>
                    <v-chip color="primary" size="small" variant="tonal">
                      {{ t('ai.relationshipPlatform') }}: {{ relationship.platform }}
                    </v-chip>
                    <v-chip color="primary" size="small" variant="tonal">
                      {{ t('ai.relationshipGroupId') }}: {{ relationship.group_id || t('common.none') }}
                    </v-chip>
                  </div>

                  <div class="relationship-meta-grid text-body-2">
                    <div>
                      <span class="text-medium-emphasis">{{ t('ai.relationshipScore') }}</span>
                      <div class="mt-1">{{ relationship.score.toFixed(1) }}</div>
                    </div>
                    <div>
                      <span class="text-medium-emphasis">{{ t('ai.relationshipMoodTags') }}</span>
                      <div class="mt-1">{{ relationshipMoodText }}</div>
                    </div>
                    <div>
                      <span class="text-medium-emphasis">{{ t('ai.relationshipLastEventAt') }}</span>
                      <div class="mt-1">{{ relationship.last_event_at || t('common.none') }}</div>
                    </div>
                  </div>

                  <div>
                    <div class="text-body-2 text-medium-emphasis mb-2">{{ t('ai.relationshipScore') }}</div>
                    <v-slider
                      v-model="relationshipForm.score"
                      color="primary"
                      hide-details
                      max="1"
                      min="-1"
                      step="0.1"
                      thumb-label
                    />
                  </div>

                  <div class="d-flex justify-end">
                    <v-btn color="primary" :loading="savingRelationship" @click="saveRelationship">
                      {{ t('ai.saveRelationship') }}
                    </v-btn>
                  </div>
                </div>
                <div v-else>
                  <div class="empty-state-text mb-3">
                    {{ t('ai.selectRelationshipTarget') }}
                  </div>
                  <div class="d-flex flex-wrap ga-3">
                    <v-btn color="primary" variant="tonal" @click="openDebugConversations()">
                      {{ t('ai.goToDebug') }}
                    </v-btn>
                    <v-btn variant="text" @click="openChatView()">
                      {{ t('ai.goToChatView') }}
                    </v-btn>
                  </div>
                </div>
              </v-sheet>
            </v-col>
          </v-row>
        </v-card-text>
      </template>

      <template v-else-if="topTab === 'skills'">
        <v-card-text class="d-flex flex-column ga-4">
          <div class="d-flex flex-wrap ga-2">
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.skills') }}: {{ skills.length }}
            </v-chip>
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.capabilities') }}: {{ skillCapabilities.length }}
            </v-chip>
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.skillReadOnly') }}: {{ readonlySkillCount }}
            </v-chip>
          </div>

          <div v-if="skills.length > 0" class="skill-card-grid">
            <v-sheet
              v-for="item in skills"
              :key="item.name"
              class="surface-gradient-card pa-4"
              rounded="lg"
            >
              <div class="d-flex flex-wrap justify-space-between ga-3">
                <div>
                  <div class="text-subtitle-1 font-weight-medium">{{ item.display_name || item.name }}</div>
                  <div class="text-body-2 text-medium-emphasis mt-1">
                    {{ item.display_description || item.description || t('common.none') }}
                  </div>
                </div>
                <v-chip color="primary" size="small" variant="tonal">
                  {{ item.risk_label || item.risk_level }}
                </v-chip>
              </div>

              <div class="d-flex flex-wrap ga-2 mt-3">
                <v-chip :color="item.read_only ? 'success' : 'default'" size="small" variant="tonal">
                  {{ t('ai.skillReadOnly') }}: {{ item.read_only ? t('ai.enabled') : t('ai.disabled') }}
                </v-chip>
                <v-chip :color="item.concurrency_safe ? 'success' : 'default'" size="small" variant="tonal">
                  {{ t('ai.skillConcurrencySafe') }}: {{ item.concurrency_safe ? t('ai.enabled') : t('ai.disabled') }}
                </v-chip>
                <v-chip :color="item.is_capability_bridge ? 'success' : 'default'" size="small" variant="tonal">
                  {{ t('ai.skillCapabilityBridge') }}: {{ item.is_capability_bridge ? t('ai.enabled') : t('ai.disabled') }}
                </v-chip>
              </div>

              <div class="mt-4">
                <div class="text-body-2 text-medium-emphasis mb-2">{{ t('ai.linkedCapabilities') }}</div>
                <div v-if="skillCapabilitiesFor(item.name).length > 0" class="d-flex flex-wrap ga-2">
                  <v-chip
                    v-for="capability in skillCapabilitiesFor(item.name)"
                    :key="`${item.name}-${capability}`"
                    color="primary"
                    size="small"
                    variant="tonal"
                  >
                    {{ capability }}
                  </v-chip>
                </div>
                <div v-else class="empty-state-text">
                  {{ t('ai.noCapabilities') }}
                </div>
              </div>
            </v-sheet>
          </div>

          <v-sheet v-else class="surface-gradient-card pa-4" rounded="lg">
            <div class="empty-state-text">{{ t('ai.noSkills') }}</div>
          </v-sheet>
        </v-card-text>
      </template>

      <template v-else>
        <v-card-text class="d-flex flex-column ga-4">
          <v-tabs v-model="debugTab" color="primary">
            <v-tab value="conversations">{{ t('ai.debugConversationTitle') }}</v-tab>
            <v-tab value="futureTasks">{{ t('ai.futureTaskTab') }}</v-tab>
            <v-tab value="tools">{{ t('ai.debugToolsTab') }}</v-tab>
          </v-tabs>

          <template v-if="debugTab === 'conversations'">
            <div class="d-flex flex-column ga-5 pt-4">
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

              <v-sheet v-if="conversations.length > 0" class="surface-gradient-card pa-4" rounded="lg">
                <div v-if="selectedConversation" class="d-flex flex-column ga-2 text-body-2">
                  <div>{{ t('ai.conversationId') }}: {{ selectedConversation.conversation_id }}</div>
                  <div>{{ t('ai.scopeType') }}: {{ selectedConversation.scope_type }}</div>
                  <div>{{ t('ai.scopeId') }}: {{ selectedConversation.scope_id }}</div>
                  <div>{{ t('ai.conversationSummary') }}: {{ selectedConversation.short_summary || t('common.none') }}</div>
                  <div>{{ t('ai.lastActiveAt') }}: {{ selectedConversation.last_active_at }}</div>
                </div>
                <div v-else class="empty-state-text">
                  {{ t('ai.noConversationSelected') }}
                </div>
              </v-sheet>

              <template v-if="conversations.length === 0 && !loadingDebug">
                <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                  <div class="empty-state-text mb-3">{{ t('ai.noConversationSelected') }}</div>
                  <div class="empty-state-hint mb-3">{{ t('ai.noConversationSelectedHint') }}</div>
                  <div class="d-flex flex-wrap ga-3">
                    <v-btn color="primary" variant="tonal" @click="openChatView()">
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

                    <v-sheet class="surface-gradient-card pa-4" rounded="lg">
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
                  <div v-if="promptPreview" class="d-flex flex-column ga-3 text-body-2">
                    <div>{{ t('ai.latestUserMessage') }}: {{ promptPreview.latest_user_message || t('common.none') }}</div>
                    <div>{{ t('ai.modelName') }}: {{ promptPreview.model_name || t('common.none') }}</div>
                    <div>{{ t('ai.personaId') }}: {{ promptPreview.persona_id || t('common.none') }}</div>
                    <div>{{ t('ai.relationshipStateTitle') }}: {{ promptPreview.relationship_context || t('common.none') }}</div>
                    <div>{{ t('ai.toolPolicyTitle') }}: {{ promptPreview.tool_policy || t('common.none') }}</div>
                    <div>{{ t('ai.socialAction') }}: {{ promptPreview.social_action || t('common.none') }}</div>
                    <div>{{ t('ai.socialToolMode') }}: {{ promptPreview.social_tool_mode || t('common.none') }}</div>
                    <div>{{ t('ai.socialReason') }}: {{ promptPreview.social_reason_text || t('common.none') }}</div>
                    <div>{{ t('ai.socialReasonCodes') }}: {{ promptPreview.social_reason_codes.join(', ') || t('common.none') }}</div>
                    <div>{{ t('ai.socialPolicySource') }}: {{ promptPreview.social_policy_source || t('common.none') }}</div>
                    <div>{{ t('ai.memoryHits') }}: {{ promptPreview.memories.length }}</div>
                    <div>{{ t('ai.toolResultsTitle') }}: {{ promptPreview.tool_results.length }}</div>
                    <pre class="ai-prompt-preview">{{ promptPreview.rendered_prompt }}</pre>
                  </div>
                  <div v-else class="empty-state-text">
                    {{ t('ai.noPromptPreview') }}
                  </div>
                </v-sheet>

                <v-data-table
                  class="page-table"
                  density="compact"
                  :headers="promptMemoryHeaders"
                  :items="promptPreview?.memories || []"
                  :items-per-page-text="t('common.itemsPerPage')"
                  :no-data-text="t('common.noData')"
                />

                <v-data-table
                  class="page-table"
                  density="compact"
                  :headers="turnHeaders"
                  :items="turns"
                  :items-per-page-text="t('common.itemsPerPage')"
                  :loading="loadingTurns"
                  :no-data-text="t('common.noData')"
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
            <div class="d-flex flex-column ga-4 pt-4">
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
            <div class="d-flex flex-column ga-4 pt-4">
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
                <v-btn color="primary" :loading="saving" @click="submitBinding(() => loadData())">
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
                      @click="removeBinding(item.binding_id, () => loadData())"
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
                  :items="debugCapabilities"
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

              <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                <div v-if="policyPreview" class="d-flex flex-column ga-2 text-body-2">
                  <div>{{ t('ai.executionEnabled') }}: {{ policyPreview.execution_enabled ? t('ai.enabled') : t('ai.disabled') }}</div>
                  <div>{{ t('ai.allowCapabilityBridge') }}: {{ policyPreview.allow_capability_bridge ? t('ai.enabled') : t('ai.disabled') }}</div>
                  <div>{{ t('ai.allowedTools') }}: {{ policyPreview.allowed_tool_names?.join(', ') || t('common.none') }}</div>
                </div>
                <div v-else class="empty-state-text">
                  {{ t('ai.noPreviewYet') }}
                </div>
              </v-sheet>

              <v-sheet class="surface-gradient-card pa-4" rounded="lg">
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
  import { useAIRelationshipTab } from '@/composables/useAIRelationshipTab'
  import { useAISkillsTab } from '@/composables/useAISkillsTab'

  const { t } = useI18n()
  const router = useRouter()

  const loading = ref(false)
  const errorMessage = ref('')
  const topTab = ref('providers')
  const debugTab = ref('conversations')

  const {
    conversations,
    loadConversationDetails,
    loadDebugData,
    loadingTurns,
    loadingDebug,
    promptPreview,
    selectedConversation,
    summarizeJsonText,
    summarizeRawPayload,
    toolExecutions,
    toolExecutionStats,
    traceIds,
    turns,
    debugForm,
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
    selectedPersona,
    startCreatePersona,
    touchPersonaField,
  } = useAIPersonasTab(t)

  const {
    canSaveProvider,
    displayedProviderErrors,
    isCreatingProvider,
    loadModelsData,
    modelBindings,
    modelProfiles,
    providerForm,
    providerTypes,
    providers,
    saveProvider,
    savingProvider,
    selectProvider,
    selectedProvider,
    startCreateProvider,
    touchProviderField,
  } = useAIModelsTab(t)

  const {
    cancelFutureTask,
    cancellingTaskId,
    futureTasks,
    loadFutureTasks,
    loadingFutureTasks,
  } = useAIFutureTasksTab(t)

  const {
    canLoadMemories,
    loadMemories,
    loadRecentTargets,
    loadingMemories,
    loadingRecentTargets,
    memories,
    memoryForm,
    recentTargets,
    selectRecentTarget,
    selectedRecentTargetId,
  } = useAIMemoryTab(t)

  const {
    loadRelationshipForTarget,
    loadRelationships,
    loadingSelectedRelationship,
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

  const providerTypeOptions = computed(() => providerTypes.value.map(value => ({
    title: providerTypeLabel(value),
    value,
  })))

  function providerTypeLabel (value: string) {
    return {
      openai_compatible: t('ai.providerTypeOpenAICompatible'),
      anthropic: t('ai.providerTypeAnthropic'),
      anthropic_compatible: t('ai.providerTypeAnthropicCompatible'),
      litellm: t('ai.providerTypeLiteLLM'),
    }[value] ?? value
  }

  const bindingHeaders = computed(() => [
    { title: t('ai.scopeType'), key: 'scope_type', sortable: false },
    { title: t('ai.scopeId'), key: 'scope_id', sortable: false },
    { title: t('ai.allowReadOnlyTools'), key: 'allow_read_only_tools', sortable: false },
    { title: t('ai.capabilityMode'), key: 'capability_mode', sortable: false },
    { title: 'Actions', key: 'actions', sortable: false, align: 'end' as const },
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

  const futureTaskHeaders = computed(() => [
    { title: t('ai.futureTaskId'), key: 'task_id', sortable: false },
    { title: t('ai.futureTaskTitle'), key: 'title', sortable: false },
    { title: t('ai.futureTaskDescription'), key: 'description', sortable: false },
    { title: t('ai.futureTaskTriggerAt'), key: 'trigger_at', sortable: false },
    { title: t('ai.futureTaskStatus'), key: 'status', sortable: false },
    { title: t('ai.createdAt'), key: 'created_at', sortable: false },
    { title: 'Actions', key: 'actions', sortable: false, align: 'end' as const },
  ])

  const memorySubjectOptions = computed(() => [
    { title: t('ai.scopeUser'), value: 'user' },
    { title: t('ai.scopeConversation'), value: 'conversation' },
  ])

  const memoryLimitOptions = [10, 20, 50, 100]

  const memoryTargetLabel = computed(() => {
    if (!memoryForm.subject_id.trim()) {
      return t('ai.selectMemoryTarget')
    }
    const subjectLabel = memorySubjectOptions.value.find(item => item.value === memoryForm.subject_type)?.title ?? memoryForm.subject_type
    return `${subjectLabel} · ${memoryForm.subject_id}`
  })

  const memoryTypeBreakdown = computed(() => {
    const counts = new Map<string, number>()
    for (const item of memories.value) {
      counts.set(item.memory_type, (counts.get(item.memory_type) ?? 0) + 1)
    }
    return Array.from(counts.entries()).map(([memoryType, count]) => ({ memoryType, count }))
  })

  const readonlySkillCount = computed(() => skills.value.filter(item => item.read_only).length)

  const recentUserTargets = computed(() => recentTargets.value.filter(item => item.subject_type === 'user'))

  const relationshipSelectionLabel = computed(() => {
    if (!relationship.value) {
      return t('ai.selectRelationshipTarget')
    }
    return relationship.value.user_id
  })

  const skillCapabilitiesByTool = computed(() => {
    const map = new Map<string, string[]>()
    for (const item of skillCapabilities.value) {
      const list = map.get(item.bound_tool_name) ?? []
      list.push(item.capability_name)
      map.set(item.bound_tool_name, list)
    }
    return map
  })

  const selectedProviderProfileCount = computed(() => {
    if (!selectedProvider.value) {
      return 0
    }
    return modelProfiles.value.filter(item => item.provider_id === selectedProvider.value?.provider_id).length
  })

  const selectedProviderBindingCount = computed(() => {
    if (!selectedProvider.value) {
      return 0
    }
    const profileIds = new Set(
      modelProfiles.value
        .filter(item => item.provider_id === selectedProvider.value?.provider_id)
        .map(item => item.profile_id),
    )
    return modelBindings.value.filter(item => profileIds.has(item.profile_id)).length
  })

  const selectedPersonaBindingCount = computed(() => {
    if (!selectedPersona.value) {
      return 0
    }
    return personaBindings.value.filter(item => item.persona_id === selectedPersona.value?.persona_id).length
  })

  const relationshipMoodText = computed(() => {
    const tags = relationship.value?.mood_tags ?? []
    if (tags.length === 0) {
      return t('common.none')
    }
    return tags.join('、')
  })

  function formatMemoryScore (value: number) {
    return value.toFixed(2)
  }

  function formatMemorySourceTurn (sourceTurnId: string | null) {
    if (!sourceTurnId) {
      return t('common.none')
    }
    return `${sourceTurnId.slice(0, 12)}...`
  }

  function openDebugConversations () {
    topTab.value = 'debug'
    debugTab.value = 'conversations'
  }

  async function openChatView () {
    await router.push({ name: 'chat' })
  }

  function skillCapabilitiesFor (toolName: string) {
    return skillCapabilitiesByTool.value.get(toolName) ?? []
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

.relationship-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.empty-state-text {
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 0.95rem;
}

.empty-state-hint {
  color: rgba(var(--v-theme-on-surface), 0.54);
  font-size: 0.85rem;
  line-height: 1.6;
}

.ai-memory-toolbar {
  align-items: end;
}

.memory-card-list {
  display: grid;
  gap: 16px;
}

.memory-content-text {
  line-height: 1.7;
  white-space: pre-wrap;
}

:deep(.page-table .v-data-table-footer__info) {
  display: none;
}

.skill-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

@media (max-width: 960px) {
  .ai-binding-form,
  .relationship-meta-grid,
  .skill-card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
