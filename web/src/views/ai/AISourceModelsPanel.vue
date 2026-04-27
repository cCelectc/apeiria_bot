<template>
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
              <div class="source-model-form pt-2">
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

      <v-sheet
        v-if="isChatCapability"
        class="surface-gradient-card pa-4 mt-4"
        rounded="lg"
      >
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

        <div v-if="sourceModels.length === 0" class="empty-state-text">
          {{ t('ai.modelProfileRequiresModel') }}
        </div>
        <template v-else>
          <div v-if="filteredModelProfiles.length > 0" class="d-flex flex-column ga-3 mb-4">
            <v-sheet
              v-for="item in filteredModelProfiles"
              :key="item.profile_id"
              class="source-model-row px-4 py-3"
              :class="{ 'source-model-row--active': item.profile_id === profileForm.profile_id }"
              rounded="xl"
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
          <div v-else class="empty-state-text mb-4">
            {{ t('ai.noModelProfiles') }}
          </div>

          <div class="source-model-form">
            <v-text-field
              v-model.trim="profileForm.name"
              density="comfortable"
              :disabled="savingProfile"
              :error-messages="displayedProfileErrors.name ? [displayedProfileErrors.name] : []"
              :label="t('ai.modelProfileName')"
              @blur="touchProfileField('name')"
            />
            <v-select
              v-model="profileForm.model_id"
              density="comfortable"
              :disabled="savingProfile"
              :error-messages="displayedProfileErrors.model_id ? [displayedProfileErrors.model_id] : []"
              :items="profileModelOptions"
              :label="t('ai.modelName')"
              @blur="touchProfileField('model_id')"
            />
            <v-select
              v-model="profileForm.task_class"
              density="comfortable"
              :disabled="savingProfile"
              :items="taskClassOptions"
              :label="t('ai.modelTaskClass')"
            />
            <v-text-field
              v-model.number="profileForm.priority"
              density="comfortable"
              :disabled="savingProfile"
              :label="t('ai.modelProfilePriority')"
              type="number"
            />
            <v-select
              v-model="profileForm.fallback_profile_id"
              clearable
              density="comfortable"
              :disabled="savingProfile"
              :items="fallbackProfileOptions"
              :label="t('ai.modelProfileFallback')"
            />
            <v-switch
              v-model="profileForm.enabled"
              color="primary"
              density="comfortable"
              :disabled="savingProfile"
              hide-details
              :label="t('ai.modelProfileEnabled')"
            />
          </div>

          <div class="d-flex justify-end mt-4">
            <v-btn color="primary" :disabled="!canSaveProfile" :loading="savingProfile" @click="saveModelProfile">
              {{ t('common.save') }}
            </v-btn>
          </div>
        </template>
      </v-sheet>
    </template>
  </v-sheet>
</template>

<script setup lang="ts">
  import type {
    AIModelCatalogItem,
    AIModelProfileItem,
    AISourceModelItem,
  } from '@/api/ai'
  import type {
    ModelFormState,
    ProfileFormState,
    SourceFormState,
  } from '@/composables/aiModels/formState'
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'

  interface ConfiguredSourceModelRow extends AISourceModelItem {
    key: string
    kind: 'configured'
  }

  interface ImportableSourceModelRow {
    key: string
    kind: 'importable'
    display_name: string
    model_identifier: string
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
  }>()

  const modelForm = defineModel<ModelFormState>('modelForm', { required: true })
  const profileForm = defineModel<ProfileFormState>('profileForm', { required: true })

  const { t } = useI18n()

  const sourceModelEditorPanel = ref<number | null>(null)
  const sourceModelSearch = ref('')
  const modelDeleteDialog = ref(false)
  const pendingDeleteModel = ref<{ modelId: string, label: string } | null>(null)

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
</script>

<style scoped>
.source-models-panel {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.source-model-list {
  display: grid;
  gap: 12px;
}

.source-model-form {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
  background: rgba(var(--v-theme-primary), 0.06);
  border-color: rgba(var(--v-theme-primary), 0.42);
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

:deep(.source-model-search) {
  min-width: min(420px, 100%);
}

@media (max-width: 960px) {
  .source-model-form {
    grid-template-columns: 1fr;
  }

  .source-model-row {
    grid-template-columns: 1fr;
  }

  .source-model-row__meta,
  .source-model-row__actions {
    justify-content: flex-start;
  }
}
</style>
