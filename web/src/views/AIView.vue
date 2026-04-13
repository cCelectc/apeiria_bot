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
                <div class="d-flex justify-space-between align-center mb-3">
                  <div class="text-subtitle-1 font-weight-medium">
                    {{ t('ai.sourcesTitle') }}
                  </div>
                  <v-btn color="primary" variant="tonal" @click="startCreateSource">
                    {{ t('ai.createSource') }}
                  </v-btn>
                </div>
                <v-sheet class="surface-gradient-card pa-2 source-list-panel" rounded="lg">
                  <template v-if="sources.length > 0">
                    <v-list class="bg-transparent" density="comfortable" lines="two">
                      <v-list-item
                        v-for="item in sources"
                        :key="item.source_id"
                        :active="item.source_id === sourceForm.source_id"
                        class="source-list-item"
                        rounded="lg"
                        @click="selectSource(item)"
                      >
                        <template #prepend>
                          <v-avatar class="source-list-item__avatar" color="primary" size="36" variant="tonal">
                            {{ sourcePresetInitial(item.preset_type) }}
                          </v-avatar>
                        </template>
                        <div class="source-list-item__body">
                          <div class="source-list-item__header">
                            <v-list-item-title>{{ item.name }}</v-list-item-title>
                            <v-chip
                              :color="item.enabled ? 'success' : 'default'"
                              size="x-small"
                              variant="tonal"
                            >
                              {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
                            </v-chip>
                          </div>
                          <v-list-item-subtitle class="source-list-item__subtitle">
                            {{ item.api_base || t('common.none') }}
                          </v-list-item-subtitle>
                          <div class="source-list-item__meta">
                            <v-chip color="primary" size="x-small" variant="tonal">
                              {{ sourcePresetLabel(item.preset_type) }}
                            </v-chip>
                          </div>
                        </div>
                        <template #append>
                          <v-btn
                            color="error"
                            icon="mdi-delete-outline"
                            size="small"
                            variant="text"
                            @click.stop="selectSource(item); removeSource()"
                          />
                        </template>
                      </v-list-item>
                    </v-list>
                  </template>
                  <div v-else class="pa-4">
                    <div class="empty-state-text">{{ t('ai.noSources') }}</div>
                    <div class="empty-state-hint mt-2">{{ t('ai.noSourcesHint') }}</div>
                  </div>
                </v-sheet>
              </v-col>

              <v-col cols="12" lg="8">
                <v-sheet class="surface-gradient-card pa-4 mb-4 source-workspace" rounded="lg">
                  <div class="d-flex flex-wrap justify-space-between align-start ga-3 mb-4">
                    <div>
                      <div class="text-h6 font-weight-medium">
                        {{ sourceForm.name || t('ai.sourceConfigTitle') }}
                      </div>
                      <div class="text-body-2 text-medium-emphasis mt-1">
                        {{ sourceForm.api_base || (isCreatingSource ? t('ai.sourceCreateHint') : t('ai.sourceConfigHint')) }}
                      </div>
                      <div class="source-summary-line mt-2">
                        <span>{{ t('ai.sourcePreset') }}：</span>
                        <strong>{{ sourcePresetLabel(sourceForm.preset_type) }}</strong>
                      </div>
                    </div>
                    <div class="d-flex flex-wrap ga-2">
                      <v-btn
                        v-if="sourceForm.source_id"
                        color="error"
                        :loading="deletingSource"
                        variant="tonal"
                        @click="removeSource"
                      >
                        {{ t('common.delete') }}
                      </v-btn>
                      <v-btn color="primary" :disabled="!canSaveSource" :loading="savingSource" @click="saveSource">
                        {{ t('ai.saveSourceConfig') }}
                      </v-btn>
                    </div>
                  </div>

                  <div class="source-config-list">
                    <div class="source-config-row">
                      <div class="source-config-row__meta">
                        <div class="source-config-row__label">{{ t('ai.sourceName') }}</div>
                        <div class="source-config-row__hint">{{ t('ai.sourceConfigNameHint') }}</div>
                      </div>
                      <v-text-field
                        v-model.trim="sourceForm.name"
                        class="source-config-row__field"
                        density="comfortable"
                        :disabled="savingSource"
                        :error-messages="displayedSourceErrors.name ? [displayedSourceErrors.name] : []"
                        hide-details="auto"
                        @blur="touchSourceField('name')"
                      />
                    </div>

                    <div class="source-config-row">
                      <div class="source-config-row__meta">
                        <div class="source-config-row__label">{{ t('ai.sourcePreset') }}</div>
                        <div class="source-config-row__hint">{{ t('ai.sourceConfigPresetHint') }}</div>
                      </div>
                      <v-select
                        v-model="sourceForm.preset_type"
                        class="source-config-row__field"
                        density="comfortable"
                        :disabled="savingSource"
                        :error-messages="displayedSourceErrors.preset_type ? [displayedSourceErrors.preset_type] : []"
                        hide-details="auto"
                        :items="sourcePresetOptions"
                        @blur="touchSourceField('preset_type')"
                      />
                    </div>

                    <div class="source-config-row">
                      <div class="source-config-row__meta">
                        <div class="source-config-row__label">{{ t('ai.sourceApiKey') }}</div>
                        <div class="source-config-row__hint">{{ t('ai.sourceConfigApiKeyHint') }}</div>
                      </div>
                      <div class="source-config-row__field source-api-key-field">
                        <v-text-field
                          density="comfortable"
                          hide-details
                          :model-value="sourcePrimaryApiKey"
                          readonly
                        />
                        <v-btn
                          class="source-api-key-field__action"
                          color="primary"
                          variant="tonal"
                          @click="openSourceApiKeysEditor"
                        >
                          {{ t('ai.sourceApiKeyManage') }}
                        </v-btn>
                      </div>
                    </div>

                    <div class="source-config-row">
                      <div class="source-config-row__meta">
                        <div class="source-config-row__label">{{ t('ai.sourceApiBase') }}</div>
                        <div class="source-config-row__hint">{{ t('ai.sourceConfigApiBaseHint') }}</div>
                      </div>
                      <v-text-field
                        v-model.trim="sourceForm.api_base"
                        class="source-config-row__field"
                        density="comfortable"
                        :disabled="savingSource"
                        hide-details
                      />
                    </div>
                  </div>

                  <v-dialog
                    v-model="sourceApiKeysDialog"
                    max-width="760"
                  >
                    <v-card rounded="xl">
                      <v-card-title class="text-h5 pt-6 px-6">
                        {{ t('ai.sourceApiKeyManageTitle') }}
                      </v-card-title>
                      <v-card-text class="px-6">
                        <div class="source-api-key-editor">
                          <div class="source-api-key-editor__composer">
                            <v-text-field
                              v-model.trim="sourceApiKeyDraftInput"
                              density="comfortable"
                              hide-details
                              :label="t('ai.sourceApiKeyNew')"
                              @keydown.enter.prevent="appendSourceApiKeyDraft"
                            />
                            <v-btn
                              color="primary"
                              variant="tonal"
                              @click="appendSourceApiKeyDraft"
                            >
                              {{ t('ai.sourceApiKeyAdd') }}
                            </v-btn>
                          </div>
                          <div class="source-api-key-editor__list">
                            <div
                              v-for="(item, index) in sourceApiKeyDraft"
                              :key="`${index}-${item}`"
                              class="source-api-key-editor__item"
                            >
                              <div class="source-api-key-editor__value">
                                {{ item }}
                              </div>
                              <v-btn
                                color="error"
                                icon="mdi-close"
                                size="small"
                                variant="text"
                                @click="removeSourceApiKeyDraft(index)"
                              />
                            </div>
                          </div>
                        </div>
                      </v-card-text>
                      <v-card-actions class="px-6 pb-6">
                        <v-spacer />
                        <v-btn variant="text" @click="sourceApiKeysDialog = false">
                          {{ t('common.cancel') }}
                        </v-btn>
                        <v-btn color="primary" variant="text" @click="applySourceApiKeyDraft">
                          {{ t('common.confirm') }}
                        </v-btn>
                      </v-card-actions>
                    </v-card>
                  </v-dialog>

                  <v-expansion-panels class="mt-3" variant="accordion">
                    <v-expansion-panel>
                      <v-expansion-panel-title>{{ t('ai.sourceAdvancedConfig') }}</v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <div class="ai-binding-form pt-2">
                          <v-text-field
                            v-model.number="sourceForm.timeout_seconds"
                            density="comfortable"
                            :disabled="savingSource"
                            hide-details
                            :label="t('ai.sourceTimeoutSeconds')"
                            type="number"
                          />
                          <v-switch
                            v-model="sourceForm.enabled"
                            color="primary"
                            density="comfortable"
                            :disabled="savingSource"
                            hide-details
                            :label="t('ai.sourceEnabled')"
                          />
                          <v-text-field
                            v-model.trim="sourceForm.proxy"
                            density="comfortable"
                            :disabled="savingSource"
                            hide-details
                            :label="t('ai.sourceProxy')"
                          />
                          <v-text-field
                            v-if="sourceForm.capability_type === 'embedding'"
                            v-model.number="sourceForm.embedding_dimensions"
                            density="comfortable"
                            :disabled="savingSource"
                            hide-details
                            :label="t('ai.sourceEmbeddingDimensions')"
                            type="number"
                          />
                          <v-text-field
                            v-if="sourceForm.capability_type === 'speech_to_text'"
                            v-model.trim="sourceForm.stt_language"
                            density="comfortable"
                            :disabled="savingSource"
                            hide-details
                            :label="t('ai.sourceSttLanguage')"
                          />
                          <v-text-field
                            v-if="sourceForm.capability_type === 'text_to_speech'"
                            v-model.trim="sourceForm.tts_voice"
                            density="comfortable"
                            :disabled="savingSource"
                            hide-details
                            :label="t('ai.sourceTtsVoice')"
                          />
                          <v-select
                            v-if="sourceForm.capability_type === 'text_to_speech'"
                            v-model="sourceForm.tts_response_format"
                            density="comfortable"
                            :disabled="savingSource"
                            hide-details
                            :items="ttsResponseFormatOptions"
                            :label="t('ai.sourceTtsFormat')"
                          />
                          <v-text-field
                            v-if="sourceForm.capability_type === 'rerank'"
                            v-model.trim="sourceForm.rerank_api_suffix"
                            density="comfortable"
                            :disabled="savingSource"
                            hide-details
                            :label="t('ai.sourceRerankApiSuffix')"
                          />
                          <v-text-field
                            v-if="sourceForm.capability_type === 'rerank'"
                            v-model.number="sourceForm.rerank_top_n"
                            density="comfortable"
                            :disabled="savingSource"
                            hide-details
                            :label="t('ai.sourceRerankTopN')"
                            type="number"
                          />
                        </div>
                      </v-expansion-panel-text>
                    </v-expansion-panel>
                  </v-expansion-panels>
                </v-sheet>

                <v-sheet class="surface-gradient-card pa-4 source-models-panel" rounded="lg">
                  <template v-if="!sourceForm.source_id">
                    <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('ai.sourceModelsTitle') }}</div>
                    <div class="empty-state-text">{{ t('ai.selectSourceFirst') }}</div>
                    <div class="empty-state-hint mt-2">{{ t('ai.selectSourceFirstHint') }}</div>
                  </template>

                  <template v-else>
                    <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-4">
                      <div class="text-subtitle-1 font-weight-medium">{{ t('ai.sourceModelsTitle') }}</div>
                      <div class="d-flex flex-wrap ga-2">
                        <v-btn
                          :disabled="!canFetchSourceModels"
                          :loading="fetchingSourceModels"
                          variant="tonal"
                          @click="pullSourceModels"
                        >
                          {{ t('ai.fetchModels') }}
                        </v-btn>
                        <v-btn
                          color="primary"
                          :disabled="!sourceForm.source_id"
                          variant="tonal"
                          @click="openCreateSourceModel"
                        >
                          {{ t('ai.customModel') }}
                        </v-btn>
                      </div>
                    </div>

                    <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-3">
                      <div class="d-flex align-center ga-3 source-models-toolbar">
                        <div class="text-subtitle-1 font-weight-medium">
                          {{ t('ai.configuredModelsTitle') }}
                        </div>
                        <div class="text-body-2 text-medium-emphasis">
                          {{ t('ai.availableModelsCount') }} {{ availableImportModelCount }}
                        </div>
                      </div>
                      <div class="d-flex flex-wrap align-center ga-3">
                        <v-text-field
                          v-model.trim="sourceModelSearch"
                          class="source-model-search"
                          clearable
                          density="comfortable"
                          hide-details
                          :label="t('ai.modelSearch')"
                          prepend-inner-icon="mdi-magnify"
                        />
                        <div class="text-body-2 text-medium-emphasis">
                          {{ t('ai.sourceModelsCount') }}：{{ unifiedSourceModels.length }}
                        </div>
                      </div>
                    </div>

                    <div v-if="loadingSourceModels" class="empty-state-hint py-6">
                      {{ t('common.loading') }}
                    </div>
                    <div v-else class="source-model-list">
                      <v-expansion-panels
                        v-model="sourceModelEditorPanel"
                        class="source-model-editor-inline"
                        variant="accordion"
                      >
                        <v-expansion-panel rounded="xl">
                          <v-expansion-panel-title>
                            {{ isCreatingModel ? t('ai.createModel') : t('ai.editModel') }}
                          </v-expansion-panel-title>
                          <v-expansion-panel-text>
                            <div class="ai-binding-form pt-2">
                              <v-text-field
                                v-model.trim="modelForm.model_identifier"
                                density="comfortable"
                                :disabled="savingModel"
                                :error-messages="displayedModelErrors.model_identifier ? [displayedModelErrors.model_identifier] : []"
                                :label="t('ai.modelIdentifier')"
                                @blur="touchModelField('model_identifier')"
                              />
                              <v-text-field
                                v-model.trim="modelForm.display_name"
                                density="comfortable"
                                :disabled="savingModel"
                                :error-messages="displayedModelErrors.display_name ? [displayedModelErrors.display_name] : []"
                                :label="t('ai.modelDisplayName')"
                                @blur="touchModelField('display_name')"
                              />
                            </div>

                            <div class="d-flex flex-wrap ga-4 mt-3">
                              <v-switch
                                v-model="modelForm.enabled"
                                color="primary"
                                density="comfortable"
                                :disabled="savingModel"
                                hide-details
                                :label="t('ai.modelEnabled')"
                              />
                              <v-switch
                                v-model="modelForm.is_default"
                                color="primary"
                                density="comfortable"
                                :disabled="savingModel"
                                hide-details
                                :label="t('ai.modelDefault')"
                              />
                            </div>

                            <div class="d-flex justify-end mt-4">
                              <v-btn color="primary" :disabled="!canSaveModel" :loading="savingModel" @click="saveSourceModel">
                                {{ t('common.save') }}
                              </v-btn>
                            </div>
                          </v-expansion-panel-text>
                        </v-expansion-panel>
                      </v-expansion-panels>

                      <template v-if="unifiedSourceModels.length > 0">
                        <v-sheet
                          v-for="item in unifiedSourceModels"
                          :key="item.key"
                          class="source-model-row px-4 py-3"
                          :class="{
                            'source-model-row--active': item.kind === 'configured' && item.model_id === modelForm.model_id,
                            'source-model-row--importable': item.kind === 'importable',
                          }"
                          rounded="xl"
                          @click="item.kind === 'configured' ? openEditSourceModel(item) : undefined"
                        >
                          <div class="source-model-row__body">
                            <div class="source-model-row__title">
                              {{ item.display_name }}
                            </div>
                            <div class="source-model-row__subtitle">
                              {{ item.model_identifier }}
                            </div>
                          </div>
                          <div v-if="item.kind === 'configured'" class="source-model-row__meta">
                            <span
                              class="source-model-row__flag"
                              :class="{ 'source-model-row__flag--success': item.enabled }"
                            >
                              {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
                            </span>
                            <span
                              v-if="item.is_default"
                              class="source-model-row__flag source-model-row__flag--primary"
                            >
                              {{ t('ai.modelDefault') }}
                            </span>
                          </div>
                          <div class="source-model-row__actions">
                            <template v-if="item.kind === 'configured'">
                              <v-btn
                                color="primary"
                                icon="mdi-pencil-outline"
                                size="small"
                                variant="text"
                                @click.stop="openEditSourceModel(item)"
                              />
                              <v-btn
                                color="primary"
                                icon="mdi-flask-outline"
                                :loading="testingModelIdentifier === item.model_identifier"
                                size="small"
                                :title="t('ai.testModel')"
                                variant="text"
                                @click.stop="testSourceModel(item.model_identifier)"
                              />
                              <v-btn
                                color="error"
                                icon="mdi-delete-outline"
                                :loading="deletingModelId === item.model_id"
                                size="small"
                                variant="text"
                                @click.stop="requestRemoveSourceModel(item)"
                              />
                            </template>
                            <template v-else>
                              <v-btn
                                color="primary"
                                :loading="importingModelIdentifier === item.model_identifier"
                                prepend-icon="mdi-plus"
                                size="small"
                                variant="tonal"
                                @click.stop="importSourceModelCatalogItem({
                                  id: item.model_identifier,
                                  name: item.display_name,
                                })"
                              >
                                {{ t('ai.importModel') }}
                              </v-btn>
                            </template>
                          </div>
                        </v-sheet>
                      </template>
                      <div v-else class="source-model-empty-state py-6">
                        <div class="empty-state-text">{{ t('common.noData') }}</div>
                      </div>
                    </div>

                    <v-dialog v-model="modelDeleteDialog" max-width="420">
                      <v-card rounded="xl">
                        <v-card-title class="text-h6 pt-6 px-6">
                          {{ t('ai.deleteModelConfirmTitle') }}
                        </v-card-title>
                        <v-card-text class="px-6">
                          {{ t('ai.deleteModelConfirmText', { name: pendingDeleteModel?.label || t('common.none') }) }}
                        </v-card-text>
                        <v-card-actions class="px-6 pb-6">
                          <v-spacer />
                          <v-btn variant="text" @click="modelDeleteDialog = false">
                            {{ t('common.cancel') }}
                          </v-btn>
                          <v-btn color="error" variant="text" @click="confirmRemoveSourceModel">
                            {{ t('common.confirm') }}
                          </v-btn>
                        </v-card-actions>
                      </v-card>
                    </v-dialog>
                  </template>
                </v-sheet>
              </v-col>
            </v-row>
          </template>
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
                          {{
                            item.subject_type === 'conversation'
                              ? t('ai.scopeConversation')
                              : item.subject_type === 'participant'
                                ? t('ai.scopeParticipant')
                                : t('ai.scopeUser')
                          }}
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
                      <v-select
                        v-model="memoryForm.memory_domain"
                        density="comfortable"
                        hide-details
                        :items="memoryDomainOptions"
                        :label="t('ai.memoryDomain')"
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
                        v-model="memoryForm.memory_type"
                        density="comfortable"
                        hide-details
                        :items="memoryTypeFilterOptions"
                        :label="t('ai.memoryType')"
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

              <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                <div class="ai-binding-form ai-memory-toolbar">
                  <v-select
                    v-model="memoryDraft.memory_domain"
                    density="comfortable"
                    hide-details
                    :items="memoryDomainOptions.filter(item => item.value)"
                    :label="t('ai.memoryDomain')"
                  />
                  <v-select
                    v-model="memoryDraft.memory_type"
                    density="comfortable"
                    hide-details
                    :items="memoryTypeOptions"
                    :label="t('ai.memoryType')"
                  />
                  <v-textarea
                    v-model.trim="memoryDraft.content"
                    auto-grow
                    density="comfortable"
                    hide-details
                    :label="t('ai.memoryContent')"
                    rows="2"
                  />
                  <v-btn
                    color="primary"
                    :disabled="!canSaveMemory"
                    :loading="savingMemory"
                    @click="saveMemory"
                  >
                    {{ t('ai.saveMemory') }}
                  </v-btn>
                </div>
              </v-sheet>

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
                        {{ item.memory_domain }}
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

                  <div class="d-flex justify-end mt-3">
                    <v-btn
                      color="error"
                      :loading="deletingMemoryId === item.memory_id"
                      size="small"
                      variant="text"
                      @click="removeMemory(item.memory_id)"
                    >
                      {{ t('common.delete') }}
                    </v-btn>
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
                <template v-if="recentRelationshipTargets.length > 0">
                  <v-list class="bg-transparent" density="comfortable" lines="two">
                    <v-list-item
                      v-for="item in recentRelationshipTargets"
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
                    <div>{{ t('ai.memoryDomainSocial') }}: {{ promptPreview.social_memory_count }}</div>
                    <div>{{ t('ai.memoryDomainKnowledge') }}: {{ promptPreview.knowledge_memory_count }}</div>
                    <div>{{ t('ai.toolResultsTitle') }}: {{ promptPreview.tool_results.length }}</div>
                    <pre class="ai-prompt-preview">{{ promptPreview.rendered_prompt }}</pre>
                  </div>
                  <div v-else class="empty-state-text">
                    {{ t('ai.noPromptPreview') }}
                  </div>
                </v-sheet>

                <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                  <div class="text-subtitle-2 font-weight-medium mb-3">
                    {{ t('ai.memoryDomainSocial') }} · {{ promptPreviewSocialMemories.length }}
                  </div>
                  <v-data-table
                    class="page-table"
                    density="compact"
                    :headers="promptMemoryHeaders"
                    :items="promptPreviewSocialMemories"
                    :items-per-page-text="t('common.itemsPerPage')"
                    :no-data-text="t('common.noData')"
                  />
                </v-sheet>

                <v-sheet class="surface-gradient-card pa-4" rounded="lg">
                  <div class="text-subtitle-2 font-weight-medium mb-3">
                    {{ t('ai.memoryDomainKnowledge') }} · {{ promptPreviewKnowledgeMemories.length }}
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
  const topTab = ref('sources')
  const debugTab = ref('conversations')
  const sourceCapabilityTab = ref('chat')
  const sourceModelEditorPanel = ref<number | null>(null)
  const sourceApiKeysDialog = ref(false)
  const sourceApiKeyDraft = ref<string[]>([])
  const sourceApiKeyDraftInput = ref('')
  const modelDeleteDialog = ref(false)
  const pendingDeleteModel = ref<{ modelId: string, label: string } | null>(null)

  const {
    conversations,
    loadConversationDetails,
    loadDebugData,
    loadingTurns,
    loadingDebug,
    promptPreview,
    promptPreviewKnowledgeMemories,
    promptPreviewSocialMemories,
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
    canFetchSourceModels,
    canSaveModel,
    canSaveSource,
    deletingModelId,
    deletingSource,
    displayedModelErrors,
    displayedSourceErrors,
    fetchedSourceModels,
    fetchingSourceModels,
    importingModelIdentifier,
    testingModelIdentifier,
    importSourceModelCatalogItem,
    loadingSourceModels,
    isCreatingModel,
    isCreatingSource,
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
    sourceForm,
    sourceModels,
    sourcePresets,
    sources,
    startCreateSource,
    startCreateSourceModel,
    testSourceModel,
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

  const ttsResponseFormatOptions = [
    { title: 'wav', value: 'wav' },
    { title: 'mp3', value: 'mp3' },
    { title: 'opus', value: 'opus' },
    { title: 'aac', value: 'aac' },
    { title: 'flac', value: 'flac' },
    { title: 'pcm', value: 'pcm' },
  ]

  const {
    cancelFutureTask,
    cancellingTaskId,
    futureTasks,
    loadFutureTasks,
    loadingFutureTasks,
  } = useAIFutureTasksTab(t)

  const {
    canLoadMemories,
    canSaveMemory,
    deletingMemoryId,
    loadMemories,
    loadRecentTargets,
    loadingMemories,
    loadingRecentTargets,
    memories,
    memoryDraft,
    memoryForm,
    recentTargets,
    removeMemory,
    saveMemory,
    savingMemory,
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

  const sourceModelSearch = ref('')

  const filteredSourceModels = computed(() => {
    const keyword = sourceModelSearch.value.trim().toLowerCase()
    if (!keyword) {
      return sourceModels.value
    }
    return sourceModels.value.filter(item => {
      const haystack = `${item.display_name} ${item.model_identifier}`.toLowerCase()
      return haystack.includes(keyword)
    })
  })

  const configuredModelIdentifiers = computed(() => new Set(
    sourceModels.value.map(item => item.model_identifier),
  ))

  const importableSourceModels = computed(() => fetchedSourceModels.value
    .filter(item => !configuredModelIdentifiers.value.has(item.id))
    .filter(item => {
      const keyword = sourceModelSearch.value.trim().toLowerCase()
      if (!keyword) {
        return true
      }
      const haystack = `${item.name} ${item.id}`.toLowerCase()
      return haystack.includes(keyword)
    })
    .map(item => ({
      key: `importable-${item.id}`,
      kind: 'importable' as const,
      display_name: item.name,
      model_identifier: item.id,
    })))

  const unifiedSourceModels = computed(() => [
    ...filteredSourceModels.value.map(item => ({
      key: `configured-${item.model_id}`,
      kind: 'configured' as const,
      ...item,
    })),
    ...importableSourceModels.value,
  ])

  const availableImportModelCount = computed(() => importableSourceModels.value.length)

  const sourcePresetOptions = computed(() => sourcePresets.value.map(item => ({
    title: item.display_name,
    value: item.preset_type,
  })))

  const sourcePrimaryApiKey = computed(() => sourceForm.api_keys[0] ?? '')

  function sourcePresetLabel (value: string) {
    return sourcePresets.value.find(item => item.preset_type === value)?.display_name ?? value
  }

  function sourcePresetInitial (value: string) {
    return sourcePresetLabel(value).slice(0, 1).toUpperCase()
  }

  function openSourceApiKeysEditor () {
    sourceApiKeyDraft.value = [...sourceForm.api_keys]
    sourceApiKeyDraftInput.value = ''
    sourceApiKeysDialog.value = true
  }

  function appendSourceApiKeyDraft () {
    const nextValue = sourceApiKeyDraftInput.value.trim()
    if (!nextValue) {
      return
    }
    sourceApiKeyDraft.value = [...sourceApiKeyDraft.value, nextValue]
    sourceApiKeyDraftInput.value = ''
  }

  function removeSourceApiKeyDraft (index: number) {
    sourceApiKeyDraft.value = sourceApiKeyDraft.value.filter((_, itemIndex) => itemIndex !== index)
  }

  function applySourceApiKeyDraft () {
    sourceForm.api_keys = [...sourceApiKeyDraft.value]
    sourceApiKeysDialog.value = false
  }

  function openCreateSourceModel () {
    startCreateSourceModel()
    sourceModelEditorPanel.value = 0
  }

  function openEditSourceModel (item: {
    model_id: string
    source_id: string
    model_identifier: string
    display_name: string
    enabled: boolean
    is_default: boolean
    extra_params: Record<string, unknown>
  }) {
    selectSourceModel(item)
    sourceModelEditorPanel.value = 0
  }

  function requestRemoveSourceModel (item: {
    model_id: string
    display_name: string
    model_identifier: string
  }) {
    pendingDeleteModel.value = {
      modelId: item.model_id,
      label: item.display_name || item.model_identifier,
    }
    modelDeleteDialog.value = true
  }

  async function confirmRemoveSourceModel () {
    if (!pendingDeleteModel.value) {
      return
    }
    const target = pendingDeleteModel.value
    modelDeleteDialog.value = false
    pendingDeleteModel.value = null
    await removeSourceModel(target.modelId)
  }

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
    { title: t('ai.memoryDomain'), key: 'memory_domain', sortable: false },
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
    { title: t('common.actions'), key: 'actions', sortable: false, align: 'end' as const },
  ])

  const memorySubjectOptions = computed(() => [
    { title: t('ai.scopeUser'), value: 'user' },
    { title: t('ai.scopeParticipant'), value: 'participant' },
    { title: t('ai.scopeConversation'), value: 'conversation' },
  ])

  const memoryDomainOptions = computed(() => [
    { title: t('common.all'), value: '' },
    { title: t('ai.memoryDomainSocial'), value: 'social' },
    { title: t('ai.memoryDomainKnowledge'), value: 'knowledge' },
  ])
  const memoryTypeOptions = computed(() => [
    { title: 'fact', value: 'fact' },
    { title: 'preference', value: 'preference' },
    { title: 'relationship', value: 'relationship' },
    { title: 'note', value: 'note' },
  ])
  const memoryTypeFilterOptions = computed(() => [
    { title: t('common.all'), value: '' },
    ...memoryTypeOptions.value,
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

  const recentRelationshipTargets = computed(() => (
    recentTargets.value.filter(item => (
      (item.subject_type === 'user' || item.subject_type === 'participant')
      && !!item.platform
      && !!item.subject_user_id
    ))
  ))

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

.source-summary-line {
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-size: 0.9rem;
  line-height: 1.6;
}

.source-list-panel {
  min-height: 100%;
}

.source-list-item {
  margin-bottom: 6px;
}

.source-list-item__avatar {
  flex-shrink: 0;
}

.source-list-item__body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  width: 100%;
}

.source-list-item__header {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.source-list-item__subtitle {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-all;
}

.source-list-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-workspace,
.source-models-panel {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.source-config-list {
  display: grid;
  gap: 14px;
}

.source-config-row {
  align-items: center;
  display: grid;
  gap: 20px;
  grid-template-columns: minmax(0, 220px) minmax(0, 1fr);
}

.source-config-row__meta {
  min-width: 0;
}

.source-config-row__label {
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.5;
}

.source-config-row__hint {
  color: rgba(var(--v-theme-on-surface), 0.54);
  font-size: 0.85rem;
  line-height: 1.5;
  margin-top: 4px;
}

.source-config-row__field {
  min-width: 0;
}

.source-model-list {
  display: grid;
  gap: 12px;
}

.source-model-editor-inline {
  margin-bottom: 4px;
}

.source-model-row {
  align-items: center;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  cursor: pointer;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto auto;
  transition: border-color 0.18s ease, background-color 0.18s ease;
}

.source-model-row:hover {
  border-color: rgba(var(--v-theme-primary), 0.28);
}

.source-model-row--active {
  border-color: rgba(var(--v-theme-primary), 0.42);
  background: rgba(var(--v-theme-primary), 0.06);
}

.source-model-row--importable {
  background: rgba(var(--v-theme-primary), 0.03);
}

.source-model-row__body {
  min-width: 0;
}

.source-model-row__title {
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.5;
}

.source-model-row__subtitle {
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 0.9rem;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-model-row__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.source-model-row__flag {
  align-items: center;
  background: rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 999px;
  color: rgba(var(--v-theme-on-surface), 0.72);
  display: inline-flex;
  font-size: 0.76rem;
  font-weight: 600;
  line-height: 1;
  min-height: 24px;
  padding: 0 10px;
}

.source-model-row__flag--success {
  background: rgba(var(--v-theme-success), 0.14);
  color: rgb(var(--v-theme-success));
}

.source-model-row__flag--primary {
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}

.source-model-row__actions {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
}

.source-models-toolbar {
  min-width: 240px;
}

.source-model-empty-state {
  align-items: center;
  display: flex;
  min-height: 72px;
}

.source-api-key-field {
  align-items: center;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto;
}

.source-api-key-field__action {
  min-width: 112px;
}

.source-api-key-editor {
  display: grid;
  gap: 20px;
}

.source-api-key-editor__composer {
  align-items: center;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto;
}

.source-api-key-editor__list {
  display: grid;
  gap: 12px;
  max-height: 320px;
  overflow-y: auto;
}

.source-api-key-editor__item {
  align-items: center;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding: 0 4px 12px;
}

.source-api-key-editor__value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.source-model-search) {
  min-width: min(420px, 100%);
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

  .source-model-row {
    grid-template-columns: 1fr;
  }

  .source-config-row {
    grid-template-columns: 1fr;
  }

  .source-model-row__meta,
  .source-model-row__actions {
    justify-content: flex-start;
  }

  .source-api-key-field,
  .source-api-key-editor__composer {
    grid-template-columns: 1fr;
  }
}
</style>
