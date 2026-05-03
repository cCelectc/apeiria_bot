<template>
  <v-sheet class="surface-gradient-card pa-4 source-models-panel">
    <template v-if="!sourceForm.source_id">
      <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('ai.sourceModelsTitle') }}</div>
      <div class="empty-state-text">{{ t('ai.selectSourceFirst') }}</div>
      <div class="empty-state-hint mt-2">{{ t('ai.selectSourceFirstHint') }}</div>
    </template>

    <template v-else>
      <div
        class="source-workflow-step source-workflow-step--section mb-4"
        :class="{ 'source-workflow-step--focused': focusedStep === 'discovery' }"
      >
        <v-chip color="primary" size="small" variant="tonal">
          {{ t('ai.setupStep.discovery') }}
        </v-chip>
        <div class="source-workflow-step__text">
          {{ t('ai.modelDiscoveryWorkflowHint') }}
        </div>
      </div>

      <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-4">
        <div class="text-subtitle-1 font-weight-medium">{{ t('ai.sourceModelsTitle') }}</div>
        <div class="d-flex flex-wrap ga-2">
          <v-btn
            :color="highlight === 'fetch' ? 'primary' : undefined"
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
      <div v-if="modelFetchDisabledReason" class="disabled-reason mb-3">
        {{ modelFetchDisabledReason }}
      </div>
      <AIWorkflowResultAlert :result="workflowResults.discovery" />

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
          <label class="workbench-field source-model-search">
            <span class="workbench-field__title">{{ t('ai.modelSearch') }}</span>
            <v-text-field
              v-model.trim="sourceModelSearch"
              :aria-label="t('ai.modelSearch')"
              class="workbench-field__control"
              clearable
              density="comfortable"
              hide-details
              prepend-inner-icon="mdi-magnify"
            />
          </label>
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
          :class="{ 'source-model-editor-inline--focused': focusedStep === 'model' || focusedStep === 'defaultModel' }"
          variant="accordion"
        >
          <v-expansion-panel>
            <v-expansion-panel-title>
              {{ isCreatingModel ? t('ai.createModel') : t('ai.editModel') }}
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div class="source-model-form workbench-form-grid pt-2">
                <label class="workbench-field">
                  <span class="workbench-field__title">{{ t('ai.modelIdentifier') }}</span>
                  <v-text-field
                    v-model.trim="modelForm.model_identifier"
                    :aria-label="t('ai.modelIdentifier')"
                    class="workbench-field__control"
                    density="comfortable"
                    :disabled="savingModel"
                    :error-messages="displayedModelErrors.model_identifier ? [displayedModelErrors.model_identifier] : []"
                    @blur="touchModelField('model_identifier')"
                  />
                </label>
                <label class="workbench-field">
                  <span class="workbench-field__title">{{ t('ai.modelDisplayName') }}</span>
                  <v-text-field
                    v-model.trim="modelForm.display_name"
                    :aria-label="t('ai.modelDisplayName')"
                    class="workbench-field__control"
                    density="comfortable"
                    :disabled="savingModel"
                    :error-messages="displayedModelErrors.display_name ? [displayedModelErrors.display_name] : []"
                    @blur="touchModelField('display_name')"
                  />
                </label>
              </div>

              <div class="source-model-switches">
                <div class="workbench-field workbench-field--switch">
                  <span class="workbench-field__title">{{ t('ai.modelEnabled') }}</span>
                  <v-switch
                    v-model="modelForm.enabled"
                    :aria-label="t('ai.modelEnabled')"
                    class="workbench-field__control"
                    color="primary"
                    density="comfortable"
                    :disabled="savingModel"
                    hide-details
                  />
                </div>
                <div class="workbench-field workbench-field--switch">
                  <span class="workbench-field__title">{{ t('ai.modelDefault') }}</span>
                  <v-switch
                    v-model="modelForm.is_default"
                    :aria-label="t('ai.modelDefault')"
                    class="workbench-field__control"
                    color="primary"
                    density="comfortable"
                    :disabled="savingModel"
                    hide-details
                  />
                </div>
              </div>

              <div class="source-model-secondary-actions mt-4">
                <v-btn prepend-icon="mdi-tune-variant" variant="tonal" @click="modelAdvancedDialog = true">
                  {{ t('ai.modelAdvancedConfigAction') }}
                </v-btn>
              </div>

              <div class="d-flex justify-end mt-4">
                <v-btn color="primary" :disabled="!canSaveModel" :loading="savingModel" @click="saveSourceModel">
                  {{ t('common.save') }}
                </v-btn>
              </div>
              <div v-if="modelSaveDisabledReason" class="disabled-reason mt-3">
                {{ modelSaveDisabledReason }}
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
        <AIWorkflowResultAlert :result="workflowResults.model" />
        <div v-if="modelImportDisabledReason" class="disabled-reason mt-3">
          {{ modelImportDisabledReason }}
        </div>

        <template v-if="unifiedSourceModels.length > 0">
          <v-sheet
            v-for="item in unifiedSourceModels"
            :key="item.key"
            class="source-model-row px-4 py-3"
            :class="{
              'source-model-row--active': item.kind === 'configured' && item.model_id === modelForm.model_id,
              'source-model-row--focused': focusedStep === 'defaultModel' && item.kind === 'configured' && item.model_id === modelForm.model_id,
              'source-model-row--importable': item.kind === 'importable',
              'source-model-row--import-target': highlight === 'import' && item.kind === 'importable',
            }"
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
              <span
                v-for="source in capabilityProvenanceSources(item.capability_provenance)"
                :key="`${item.model_id}-${source}`"
                class="source-model-row__flag"
                :class="provenanceSourceClass(source)"
              >
                {{ source }}
              </span>
            </div>
            <div v-else class="source-model-row__meta">
              <span
                v-for="source in capabilityProvenanceSources(item.capability_provenance)"
                :key="`${item.key}-${source}`"
                class="source-model-row__flag"
                :class="provenanceSourceClass(source)"
              >
                {{ source }}
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
                  :disabled="!canTestModels"
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
                  :disabled="!!importingModelIdentifier && importingModelIdentifier !== item.model_identifier"
                  :loading="importingModelIdentifier === item.model_identifier"
                  prepend-icon="mdi-plus"
                  size="small"
                  variant="tonal"
                  @click.stop="importSourceModelCatalogItem({
                    id: item.model_identifier,
                    name: item.display_name,
                    capability_metadata: item.capability_metadata,
                    default_options: item.default_options,
                    capability_provenance: item.capability_provenance,
                  })"
                >
                  {{ t('ai.importModel') }}
                </v-btn>
              </template>
            </div>
          </v-sheet>
        </template>
        <EmptyState
          v-else
          action-icon="mdi-plus"
          :action-label="t('ai.customModel')"
          icon="mdi-cube-outline"
          :text="modelEmptyText"
          :title="t('ai.modelEmptyTitle')"
          @action="openCreateSourceModel"
        />
      </div>

      <v-dialog v-model="modelDeleteDialog" max-width="420">
        <v-card>
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

      <v-sheet
        v-if="isChatCapability"
        class="surface-gradient-card pa-4 mt-4"
        :class="{ 'source-model-stage--focused': focusedStep === 'profile' }"
      >
        <div class="source-workflow-step mb-4">
          <v-chip color="primary" size="small" variant="tonal">
            {{ t('ai.setupStep.profile') }}
          </v-chip>
          <div class="source-workflow-step__text">
            {{ t('ai.profileWorkflowHint') }}
          </div>
        </div>

        <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-4">
          <div class="d-flex flex-wrap ga-2">
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.modelProfiles') }}: {{ modelProfileCount }}
            </v-chip>
            <v-chip color="primary" size="small" variant="tonal">
              {{ isCreatingProfile ? t('ai.createModelProfile') : t('ai.editModel') }}
            </v-chip>
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.scopeBindings') }}: {{ selectedModelBindingCount }}
            </v-chip>
          </div>
          <v-btn color="primary" variant="tonal" @click="startCreateModelProfile">
            {{ t('ai.createModelProfile') }}
          </v-btn>
        </div>

        <EmptyState
          v-if="sourceModels.length === 0"
          icon="mdi-account-cog-outline"
          :text="t('ai.modelProfileRequiresModel')"
          :title="t('ai.profileEmptyTitle')"
        />
        <template v-else>
          <div v-if="filteredModelProfiles.length > 0" class="d-flex flex-column ga-3 mb-4">
            <v-sheet
              v-for="item in filteredModelProfiles"
              :key="item.profile_id"
              class="source-model-row px-4 py-3"
              :class="{
                'source-model-row--active': item.profile_id === profileForm.profile_id,
                'source-model-row--focused': focusedStep === 'profile' && item.profile_id === profileForm.profile_id,
              }"
              @click="selectModelProfile(item)"
            >
              <div class="source-model-row__body">
                <div class="source-model-row__title">{{ item.name }}</div>
                <div class="source-model-row__subtitle">
                  {{ item.task_class }} · {{ item.priority }}
                </div>
              </div>
              <div class="source-model-row__meta">
                <span
                  class="source-model-row__flag"
                  :class="{ 'source-model-row__flag--success': item.enabled }"
                >
                  {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
                </span>
              </div>
            </v-sheet>
          </div>
          <EmptyState
            v-else
            action-icon="mdi-plus"
            :action-label="t('ai.createModelProfile')"
            class="mb-4"
            icon="mdi-account-cog-outline"
            :text="t('ai.profileEmptyText')"
            :title="t('ai.profileEmptyTitle')"
            @action="startCreateModelProfile"
          />

          <div class="source-model-form workbench-form-grid">
            <label class="workbench-field">
              <span class="workbench-field__title">{{ t('ai.modelProfileName') }}</span>
              <v-text-field
                v-model.trim="profileForm.name"
                :aria-label="t('ai.modelProfileName')"
                class="workbench-field__control"
                density="comfortable"
                :disabled="savingProfile"
                :error-messages="displayedProfileErrors.name ? [displayedProfileErrors.name] : []"
                @blur="touchProfileField('name')"
              />
            </label>
            <label class="workbench-field">
              <span class="workbench-field__title">{{ t('ai.modelName') }}</span>
              <v-select
                v-model="profileForm.model_id"
                :aria-label="t('ai.modelName')"
                class="workbench-field__control"
                density="comfortable"
                :disabled="savingProfile"
                :error-messages="displayedProfileErrors.model_id ? [displayedProfileErrors.model_id] : []"
                :items="profileModelOptions"
                @blur="touchProfileField('model_id')"
              />
            </label>
            <label class="workbench-field">
              <span class="workbench-field__title">{{ t('ai.modelTaskClass') }}</span>
              <v-select
                v-model="profileForm.task_class"
                :aria-label="t('ai.modelTaskClass')"
                class="workbench-field__control"
                density="comfortable"
                :disabled="savingProfile"
                :items="taskClassOptions"
              />
            </label>
            <label class="workbench-field">
              <span class="workbench-field__title">{{ t('ai.modelProfilePriority') }}</span>
              <v-text-field
                v-model.number="profileForm.priority"
                :aria-label="t('ai.modelProfilePriority')"
                class="workbench-field__control"
                density="comfortable"
                :disabled="savingProfile"
                type="number"
              />
            </label>
            <label class="workbench-field">
              <span class="workbench-field__title">{{ t('ai.modelProfileFallback') }}</span>
              <v-select
                v-model="profileForm.fallback_profile_id"
                :aria-label="t('ai.modelProfileFallback')"
                class="workbench-field__control"
                clearable
                density="comfortable"
                :disabled="savingProfile"
                :items="fallbackProfileOptions"
              />
            </label>
            <div class="workbench-field workbench-field--switch">
              <span class="workbench-field__title">{{ t('ai.modelProfileEnabled') }}</span>
              <v-switch
                v-model="profileForm.enabled"
                :aria-label="t('ai.modelProfileEnabled')"
                class="workbench-field__control"
                color="primary"
                density="comfortable"
                :disabled="savingProfile"
                hide-details
              />
            </div>
          </div>

          <div class="d-flex justify-end mt-4">
            <v-btn color="primary" :disabled="!canSaveProfile" :loading="savingProfile" @click="saveModelProfile">
              {{ t('common.save') }}
            </v-btn>
          </div>
          <div v-if="profileSaveDisabledReason" class="disabled-reason mt-3">
            {{ profileSaveDisabledReason }}
          </div>
          <AIWorkflowResultAlert :result="workflowResults.profile" />
        </template>
      </v-sheet>

      <v-sheet
        v-if="workflow.selectedModel"
        class="surface-gradient-card pa-4 mt-4 model-validation-panel"
        :class="{ 'source-model-stage--focused': focusedStep === 'validation' }"
      >
        <div class="d-flex flex-wrap justify-space-between align-center ga-3">
          <div>
            <div class="text-subtitle-1 font-weight-medium">
              {{ t('ai.setupStep.validation') }}
            </div>
            <div class="empty-state-hint mt-1">
              {{ t('ai.modelValidationHint', { model: workflow.selectedModel.display_name }) }}
            </div>
          </div>
          <v-btn
            color="primary"
            :disabled="!canTestModels"
            :loading="testingModelIdentifier === workflow.selectedModel.model_identifier"
            prepend-icon="mdi-flask-outline"
            variant="tonal"
            @click="testSourceModel(workflow.selectedModel.model_identifier)"
          >
            {{ t('ai.testModel') }}
          </v-btn>
        </div>
        <div v-if="modelTestDisabledReason" class="disabled-reason mt-3">
          {{ modelTestDisabledReason }}
        </div>
        <AIWorkflowResultAlert :result="workflowResults.validation" />
      </v-sheet>

      <PopupPanel
        v-model="modelAdvancedDialog"
        :close-label="t('common.close')"
        max-width="860"
        :title="t('ai.modelAdvancedConfigAction')"
      >
        <div class="source-model-form workbench-form-grid">
          <label class="workbench-field workbench-field--wide">
            <span class="workbench-field__title">{{ t('ai.capabilityMetadata') }}</span>
            <v-textarea
              v-model="modelForm.capability_metadata_json"
              :aria-label="t('ai.capabilityMetadata')"
              auto-grow
              class="workbench-field__control"
              density="comfortable"
              :disabled="savingModel"
              hide-details
              rows="3"
            />
          </label>
          <label class="workbench-field workbench-field--wide">
            <span class="workbench-field__title">{{ t('ai.defaultOptions') }}</span>
            <v-textarea
              v-model="modelForm.default_options_json"
              :aria-label="t('ai.defaultOptions')"
              auto-grow
              class="workbench-field__control"
              density="comfortable"
              :disabled="savingModel"
              hide-details
              rows="3"
            />
          </label>
          <label class="workbench-field workbench-field--wide">
            <span class="workbench-field__title">{{ t('ai.capabilityProvenance') }}</span>
            <v-textarea
              v-model="modelForm.capability_provenance_json"
              :aria-label="t('ai.capabilityProvenance')"
              auto-grow
              class="workbench-field__control"
              density="comfortable"
              :disabled="savingModel"
              hide-details
              rows="3"
            />
          </label>
        </div>
      </PopupPanel>
    </template>
  </v-sheet>
</template>

<script setup lang="ts">
  import type {
    AIModelCatalogItem,
    AIModelProfileItem,
    AISourceModelItem,
  } from '@/api/ai/types'
  import type {
    ModelFormState,
    ProfileFormState,
    SourceFormState,
  } from '@/composables/aiModels/formState'
  import type {
    AISetupWorkflow,
    AIWorkflowOperationResult,
    AIWorkflowResultStage,
  } from '@/composables/aiModels/setupWorkflow'
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { EmptyState, PopupPanel } from '@/components/workbench'
  import AIWorkflowResultAlert from './AIWorkflowResultAlert.vue'

  interface ConfiguredSourceModelRow extends AISourceModelItem {
    key: string
    kind: 'configured'
  }

  interface ImportableSourceModelRow {
    key: string
    kind: 'importable'
    display_name: string
    model_identifier: string
    capability_metadata: Record<string, unknown>
    default_options: Record<string, unknown>
    capability_provenance: Record<string, unknown>
  }

  const props = defineProps<{
    canFetchSourceModels: boolean
    canSaveModel: boolean
    canSaveProfile: boolean
    deletingModelId: string
    displayedModelErrors: {
      model_identifier: string
      display_name: string
    }
    displayedProfileErrors: {
      name: string
      model_id: string
    }
    fallbackProfileOptions: Array<{
      title: string
      value: string
    }>
    fetchedSourceModels: AIModelCatalogItem[]
    fetchingSourceModels: boolean
    filteredModelProfiles: AIModelProfileItem[]
    focusedStep?: AISetupWorkflow['nextAction']['targetStep']
    highlight?: string
    importingModelIdentifier: string
    isChatCapability: boolean
    isCreatingModel: boolean
    isCreatingProfile: boolean
    loadingSourceModels: boolean
    modelProfileCount: number
    profileModelOptions: Array<{
      title: string
      value: string
    }>
    pullSourceModels: () => void | Promise<void>
    removeSourceModel: (modelId: string) => void | Promise<void>
    saveModelProfile: () => void | Promise<void>
    saveSourceModel: () => void | Promise<void>
    savingModel: boolean
    savingProfile: boolean
    selectModelProfile: (item: AIModelProfileItem) => void | Promise<void>
    selectSourceModel: (item: AISourceModelItem) => void | Promise<void>
    selectedModelBindingCount: number
    sourceForm: SourceFormState
    sourceModels: AISourceModelItem[]
    startCreateModelProfile: () => void
    startCreateSourceModel: () => void
    taskClassOptions: Array<{
      title: string
      value: string
    }>
    testSourceModel: (modelIdentifier: string) => void | Promise<void>
    testingModelIdentifier: string
    touchModelField: (field: 'model_identifier' | 'display_name') => void
    touchProfileField: (field: 'name' | 'model_id') => void
    importSourceModelCatalogItem: (item: AIModelCatalogItem) => void | Promise<void>
    workflow: AISetupWorkflow
    workflowResults: Record<AIWorkflowResultStage, AIWorkflowOperationResult | null>
  }>()

  const modelForm = defineModel<ModelFormState>('modelForm', { required: true })
  const profileForm = defineModel<ProfileFormState>('profileForm', { required: true })

  const { t } = useI18n()

  const sourceModelEditorPanel = ref<number | null>(null)
  const sourceModelSearch = ref('')
  const modelAdvancedDialog = ref(false)
  const modelDeleteDialog = ref(false)
  const pendingDeleteModel = ref<{ modelId: string, label: string } | null>(null)
  const shouldOpenModelEditor = computed(() => (
    props.focusedStep === 'model'
    || props.focusedStep === 'defaultModel'
  ))

  const filteredSourceModels = computed(() => {
    const keyword = sourceModelSearch.value.trim().toLowerCase()
    if (!keyword) {
      return props.sourceModels
    }
    return props.sourceModels.filter(item => {
      const haystack = `${item.display_name} ${item.model_identifier}`.toLowerCase()
      return haystack.includes(keyword)
    })
  })

  const configuredModelIdentifiers = computed(() => new Set(
    props.sourceModels.map(item => item.model_identifier),
  ))

  const importableSourceModels = computed<ImportableSourceModelRow[]>(() => props.fetchedSourceModels
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
      kind: 'importable',
      display_name: item.name,
      model_identifier: item.id,
      capability_metadata: item.capability_metadata,
      default_options: item.default_options,
      capability_provenance: item.capability_provenance,
    })))

  const unifiedSourceModels = computed<Array<ConfiguredSourceModelRow | ImportableSourceModelRow>>(() => [
    ...filteredSourceModels.value.map(item => ({
      key: `configured-${item.model_id}`,
      kind: 'configured' as const,
      ...item,
    })),
    ...importableSourceModels.value,
  ])

  const availableImportModelCount = computed(() => importableSourceModels.value.length)
  const canTestModels = computed(() => (
    props.canFetchSourceModels && !props.testingModelIdentifier
  ))
  const modelFetchDisabledReason = computed(() => {
    if (props.fetchingSourceModels || props.canFetchSourceModels) {
      return ''
    }
    if (!props.sourceForm.source_id) {
      return t('ai.selectSourceFirstHint')
    }
    if (props.workflow.connectionIssues.length > 0) {
      return t('ai.modelFetchDisabledConnection')
    }
    return t('ai.modelFetchDisabled')
  })
  const modelSaveDisabledReason = computed(() => {
    if (props.savingModel || props.canSaveModel) {
      return ''
    }
    if (!modelForm.value.model_identifier.trim()) {
      return t('ai.modelIdentifierRequired')
    }
    if (!modelForm.value.display_name.trim()) {
      return t('ai.modelDisplayNameRequired')
    }
    return props.displayedModelErrors.model_identifier
      || props.displayedModelErrors.display_name
      || (props.sourceForm.source_id ? t('ai.modelSaveDisabledNoChanges') : t('ai.selectSourceFirstHint'))
  })
  const modelImportDisabledReason = computed(() => (
    props.importingModelIdentifier ? t('ai.modelImportRunning') : ''
  ))
  const modelEmptyText = computed(() => (
    props.workflow.connectionIssues.length > 0
      ? t('ai.modelEmptyConnectionText')
      : t('ai.modelEmptyText')
  ))
  const profileSaveDisabledReason = computed(() => {
    if (props.savingProfile || props.canSaveProfile) {
      return ''
    }
    if (!profileForm.value.name.trim()) {
      return t('ai.modelProfileNameRequired')
    }
    if (!profileForm.value.model_id.trim()) {
      return t('ai.modelProfileModelRequired')
    }
    return props.displayedProfileErrors.name
      || props.displayedProfileErrors.model_id
      || t('ai.profileSaveDisabledNoChanges')
  })
  const modelTestDisabledReason = computed(() => {
    if (canTestModels.value) {
      return ''
    }
    if (props.workflow.connectionIssues.length > 0) {
      return t('ai.modelTestDisabledConnection')
    }
    if (props.testingModelIdentifier) {
      return t('ai.modelTestRunning')
    }
    return t('ai.modelTestDisabled')
  })

  function openCreateSourceModel () {
    props.startCreateSourceModel()
    sourceModelEditorPanel.value = 0
  }

  function openEditSourceModel (item: AISourceModelItem) {
    props.selectSourceModel(item)
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
    await props.removeSourceModel(target.modelId)
  }

  watch(shouldOpenModelEditor, shouldOpen => {
    if (shouldOpen) {
      sourceModelEditorPanel.value = 0
    }
  }, { immediate: true })

  function capabilityProvenanceSources (value: Record<string, unknown> | undefined) {
    if (!value || typeof value !== 'object') {
      return []
    }
    const sources = new Set<string>()
    for (const item of Object.values(value)) {
      if (!item || typeof item !== 'object') {
        continue
      }
      const source = (item as { source?: unknown }).source
      if (typeof source === 'string' && source.trim()) {
        sources.add(source.trim())
      }
    }
    return [...sources].slice(0, 4)
  }

  function provenanceSourceClass (source: string) {
    if (source === 'owner_override') {
      return 'source-model-row__flag--owner'
    }
    if (source === 'upstream_catalog') {
      return 'source-model-row__flag--reported'
    }
    if (source === 'model_template') {
      return 'source-model-row__flag--template'
    }
    return ''
  }
</script>

<style scoped>
.source-models-panel {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.source-model-list {
  display: grid;
  gap: 12px;
}

.source-model-editor-inline {
  margin-bottom: 4px;
}

.source-model-editor-inline--focused {
  border: 1px solid rgba(var(--v-theme-primary), 0.34);
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.12);
}

.source-model-switches {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-top: 14px;
}

.source-model-secondary-actions {
  display: flex;
  justify-content: flex-start;
}

.source-workflow-step {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.source-workflow-step--section {
  border: 1px solid transparent;
  padding: 10px 12px;
}

.source-workflow-step--focused,
.source-model-stage--focused {
  border-color: rgba(var(--v-theme-primary), 0.36) !important;
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.12);
}

.source-workflow-step__text {
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.88rem;
  line-height: 1.5;
}

.disabled-reason {
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 0.82rem;
  line-height: 1.5;
}

.model-validation-panel {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
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
  background: rgba(var(--v-theme-primary), 0.06);
  border-color: rgba(var(--v-theme-primary), 0.42);
}

.source-model-row--importable {
  background: rgba(var(--v-theme-primary), 0.03);
}

.source-model-row--focused,
.source-model-row--import-target {
  border-color: rgba(var(--v-theme-primary), 0.56);
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.18);
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

.source-model-row__flag--owner {
  background: rgba(var(--v-theme-warning), 0.16);
  color: rgb(var(--v-theme-warning));
}

.source-model-row__flag--reported {
  background: rgba(var(--v-theme-info), 0.14);
  color: rgb(var(--v-theme-info));
}

.source-model-row__flag--template {
  background: rgba(var(--v-theme-secondary), 0.14);
  color: rgb(var(--v-theme-secondary));
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

.source-model-search {
  min-width: min(420px, 100%);
}

@media (max-width: 960px) {
  .source-model-row {
    grid-template-columns: 1fr;
  }

  .source-model-row__meta,
  .source-model-row__actions {
    justify-content: flex-start;
  }
}
</style>
