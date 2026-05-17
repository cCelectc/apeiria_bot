<script setup lang="ts">
import type {
  AIModelCatalogItem,
  AIModelProfileItem,
  AISourceModelItem,
} from '@/api/ai'
import {
  Brain,
  CheckCircle2,
  CircleAlert,
  FlaskConical,
  KeyRound,
  Plus,
  RefreshCw,
  Search,
  ServerCog,
  Settings,
  Trash2,
} from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  EmptyState,
  FormField,
  LoadingSkeleton,
  PageScaffold,
  Panel,
  SelectableList,
  SelectableListItem,
  SplitPane,
} from '@/components/management'
import { Badge, type BadgeVariants } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useAIModelsTab } from '@/composables/useAIModelsTab'
import {
  normalizeAICapabilityRouteValue,
  normalizeAISetupRouteIntent,
  resolveAIModelFlowFocus,
  type AISourceCapabilityRouteValue,
  type AISetupRouteIntent,
} from '@/utils/aiRouteState'

type SourceAdvancedField =
  | 'capability_metadata_json'
  | 'capability_provenance_json'
  | 'default_options_json'
type ModelAdvancedField =
  | 'capability_metadata_json'
  | 'capability_provenance_json'
  | 'default_options_json'

interface UnifiedConfiguredSourceModel extends AISourceModelItem {
  key: string
  kind: 'configured'
}

interface UnifiedImportableSourceModel {
  capability_metadata: Record<string, unknown>
  capability_provenance: Record<string, unknown>
  default_options: Record<string, unknown>
  display_name: string
  key: string
  kind: 'importable'
  model_identifier: string
}

const { t } = useI18n()
defineProps<{
  embedded?: boolean
}>()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const sourceCapabilityTab = ref<AISourceCapabilityRouteValue>('chat')
const appliedSetupIntentKey = ref('')
const sourceSearch = ref('')
const sourceModelSearch = ref('')
const sourceApiKeysDialog = ref(false)
const sourceApiKeyDraft = ref<string[]>([])
const sourceApiKeyDraftInput = ref('')
const sourceAdvancedDialog = ref(false)
const modelAdvancedDialog = ref(false)
const modelDeleteDialog = ref(false)
const pendingDeleteModel = ref<{ label: string, modelId: string } | null>(null)
let applyingRouteState = false

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
  importSourceModelCatalogItem,
  importingModelIdentifier,
  isChatCapability,
  isCreatingModel,
  isCreatingProfile,
  isCreatingSource,
  loadModelsData,
  loadingSourceModels,
  loadingSources,
  modelForm,
  modelProfileCount,
  profileForm,
  profileModelOptions,
  providerDetailMode,
  pullSourceModels,
  removeSource,
  removeSourceModel,
  saveModelProfile,
  saveSource,
  saveSourceModel,
  savingModel,
  savingProfile,
  savingSource,
  selectModelProfile,
  selectSource,
  selectSourceModel,
  selectSourceProtocol,
  selectedModelBindingCount,
  setupWorkflow,
  sourceForm,
  sourceModels,
  sourcePresets,
  sources,
  startCreateModelProfile,
  startCreateSource,
  startCreateSourceModel,
  taskClassOptions,
  testSourceModel,
  testingModelIdentifier,
  touchModelField,
  touchProfileField,
  touchSourceField,
  workflowResults,
} = useAIModelsTab(sourceCapabilityTab, t)

const sourceCapabilityOptions = computed(() => [
  { title: t('ai.sourceCapabilityChat'), value: 'chat' as const },
  { title: t('ai.sourceCapabilityStt'), value: 'stt' as const },
  { title: t('ai.sourceCapabilityTts'), value: 'tts' as const },
  { title: t('ai.sourceCapabilityEmbedding'), value: 'embedding' as const },
  { title: t('ai.sourceCapabilityRerank'), value: 'rerank' as const },
])
const modelFlowFocus = computed(() => resolveAIModelFlowFocus({
  intent: currentSetupRouteIntent(),
  workflowDependency: setupWorkflow.value.dependency,
  workflowNextAction: setupWorkflow.value.nextAction.kind,
  workflowTargetStep: setupWorkflow.value.nextAction.targetStep,
}))
const filteredSources = computed(() => {
  const keyword = sourceSearch.value.trim().toLowerCase()
  if (!keyword) {
    return sources.value
  }
  return sources.value.filter(item => (
    `${item.name} ${item.api_base ?? ''} ${item.preset_type}`.toLowerCase().includes(keyword)
  ))
})
const sourcePresetOptions = computed(() => sourcePresets.value.map(item => ({
  title: item.display_name,
  value: item.preset_type,
})))
const configuredModelIdentifiers = computed(() => new Set(
  sourceModels.value.map(item => item.model_identifier),
))
const filteredSourceModels = computed(() => {
  const keyword = sourceModelSearch.value.trim().toLowerCase()
  if (!keyword) {
    return sourceModels.value
  }
  return sourceModels.value.filter(item => (
    `${item.display_name} ${item.model_identifier}`.toLowerCase().includes(keyword)
  ))
})
const importableSourceModels = computed<UnifiedImportableSourceModel[]>(() => (
  fetchedSourceModels.value
    .filter(item => !configuredModelIdentifiers.value.has(item.id))
    .filter(item => {
      const keyword = sourceModelSearch.value.trim().toLowerCase()
      if (!keyword) {
        return true
      }
      return `${item.name} ${item.id}`.toLowerCase().includes(keyword)
    })
    .map(item => ({
      capability_metadata: item.capability_metadata,
      capability_provenance: item.capability_provenance,
      default_options: item.default_options,
      display_name: item.name,
      key: `importable-${item.id}`,
      kind: 'importable' as const,
      model_identifier: item.id,
    }))
))
const unifiedSourceModels = computed<Array<UnifiedConfiguredSourceModel | UnifiedImportableSourceModel>>(() => [
  ...filteredSourceModels.value.map(item => ({
    ...item,
    key: `configured-${item.model_id}`,
    kind: 'configured' as const,
  })),
  ...importableSourceModels.value,
])
const canTestModels = computed(() => (
  canFetchSourceModels.value && !testingModelIdentifier.value
))
const sourcePrimaryApiKey = computed({
  get: () => sourceForm.api_keys[0] ?? '',
  set: value => {
    const nextValue = value.trim()
    const nextKeys = [...sourceForm.api_keys]
    if (nextValue) {
      nextKeys[0] = nextValue
    } else {
      nextKeys.splice(0, 1)
    }
    sourceForm.api_keys = nextKeys
  },
})
const extraSourceApiKeys = computed(() => sourceForm.api_keys.slice(1))
const providerDetailTitle = computed(() => {
  if (providerDetailMode.value === 'creating') {
    return t('ai.creatingSource')
  }
  if (providerDetailMode.value === 'selected') {
    return sourceForm.name || t('ai.sourceConfigTitle')
  }
  return t('ai.sourceProviderEmptyTitle')
})
const providerDetailText = computed(() => {
  if (providerDetailMode.value === 'creating') {
    return t('ai.sourceCreateHint')
  }
  if (providerDetailMode.value === 'selected') {
    return sourceForm.api_base || t('ai.sourceConfigHint')
  }
  return t('ai.sourceProviderSelectText')
})
const providerSaveDisabledReason = computed(() => {
  if (savingSource.value || canSaveSource.value) {
    return ''
  }
  if (!sourceForm.name.trim()) {
    return t('ai.sourceNameRequired')
  }
  if (!sourceForm.preset_type.trim()) {
    return t('ai.sourcePresetRequired')
  }
  return displayedSourceErrors.value.name
    || displayedSourceErrors.value.preset_type
    || t('ai.sourceSaveDisabledNoChanges')
})
const modelFetchDisabledReason = computed(() => {
  if (fetchingSourceModels.value || canFetchSourceModels.value) {
    return ''
  }
  if (!sourceForm.source_id) {
    return t('ai.selectSourceFirstHint')
  }
  if (setupWorkflow.value.connectionIssues.length > 0) {
    return t('ai.modelFetchDisabledConnection')
  }
  return t('ai.modelFetchDisabled')
})
const modelSaveDisabledReason = computed(() => {
  if (savingModel.value || canSaveModel.value) {
    return ''
  }
  if (!modelForm.model_identifier.trim()) {
    return t('ai.modelIdentifierRequired')
  }
  if (!modelForm.display_name.trim()) {
    return t('ai.modelDisplayNameRequired')
  }
  return displayedModelErrors.value.model_identifier
    || displayedModelErrors.value.display_name
    || (sourceForm.source_id ? t('ai.modelSaveDisabledNoChanges') : t('ai.selectSourceFirstHint'))
})
const profileSaveDisabledReason = computed(() => {
  if (savingProfile.value || canSaveProfile.value) {
    return ''
  }
  if (!profileForm.name.trim()) {
    return t('ai.modelProfileNameRequired')
  }
  if (!profileForm.model_id.trim()) {
    return t('ai.modelProfileModelRequired')
  }
  return displayedProfileErrors.value.name
    || displayedProfileErrors.value.model_id
    || t('ai.profileSaveDisabledNoChanges')
})
const modelTestDisabledReason = computed(() => {
  if (canTestModels.value) {
    return ''
  }
  if (setupWorkflow.value.connectionIssues.length > 0) {
    return t('ai.modelTestDisabledConnection')
  }
  if (testingModelIdentifier.value) {
    return t('ai.modelTestRunning')
  }
  return t('ai.modelTestDisabled')
})
const modelEmptyText = computed(() => (
  setupWorkflow.value.connectionIssues.length > 0
    ? t('ai.modelEmptyConnectionText')
    : t('ai.modelEmptyText')
))
const ttsResponseFormatOptions = [
  { title: 'wav', value: 'wav' },
  { title: 'mp3', value: 'mp3' },
  { title: 'opus', value: 'opus' },
  { title: 'aac', value: 'aac' },
  { title: 'flac', value: 'flac' },
  { title: 'pcm', value: 'pcm' },
]

async function loadData() {
  loading.value = true
  errorMessage.value = ''
  try {
    await loadModelsData()
    applySetupRouteIntent()
  } catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : t('ai.loadFailed')
  } finally {
    loading.value = false
  }
}

function sourcePresetLabel(value: string) {
  return sourcePresets.value.find(item => item.preset_type === value)?.display_name ?? value
}

function sourcePresetInitial(value: string) {
  return sourcePresetLabel(value).slice(0, 1).toUpperCase()
}

function currentSetupRouteIntent(): AISetupRouteIntent | '' {
  return normalizeAISetupRouteIntent(route.query.intent)
}

function applyRouteState() {
  const nextSourceCapabilityTab = normalizeAICapabilityRouteValue(route.query.capability)
  if (sourceCapabilityTab.value === nextSourceCapabilityTab) {
    return
  }
  applyingRouteState = true
  sourceCapabilityTab.value = nextSourceCapabilityTab
  applyingRouteState = false
}

function handleCapabilityUpdate(value: unknown) {
  if (typeof value === 'string') {
    sourceCapabilityTab.value = normalizeAICapabilityRouteValue(value)
  }
}

function syncRouteQuery() {
  const nextQuery: Record<string, string> = {
    ...stringQuery(route.query),
    capability: sourceCapabilityTab.value,
  }
  if (typeof route.query.intent === 'string' && route.query.intent) {
    nextQuery.intent = route.query.intent
  }
  if (route.query.capability === nextQuery.capability) {
    return
  }
  void router.replace({ query: nextQuery })
}

function applySetupRouteIntent() {
  const intent = currentSetupRouteIntent()
  if (!intent) {
    return
  }
  const key = `${sourceCapabilityTab.value}:${intent}:${sourceForm.source_id}`
  if (appliedSetupIntentKey.value === key) {
    return
  }
  appliedSetupIntentKey.value = key
  if (intent === 'createProvider') {
    startCreateSource()
    return
  }
  if (intent === 'createModel') {
    if (providerDetailMode.value !== 'empty') {
      startCreateSourceModel()
    }
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
    if (providerDetailMode.value !== 'empty') {
      startCreateModelProfile()
    }
  }
}

function openSourceApiKeysEditor() {
  sourceApiKeyDraft.value = [...sourceForm.api_keys]
  sourceApiKeyDraftInput.value = ''
  sourceApiKeysDialog.value = true
}

function appendSourceApiKeyDraft() {
  const nextValue = sourceApiKeyDraftInput.value.trim()
  if (!nextValue) {
    return
  }
  sourceApiKeyDraft.value = [...sourceApiKeyDraft.value, nextValue]
  sourceApiKeyDraftInput.value = ''
}

function removeSourceApiKeyDraft(index: number) {
  sourceApiKeyDraft.value = sourceApiKeyDraft.value.filter((_, itemIndex) => (
    itemIndex !== index
  ))
}

function removeExtraSourceApiKey(index: number) {
  sourceForm.api_keys = sourceForm.api_keys.filter((_, itemIndex) => (
    itemIndex !== index + 1
  ))
}

function applySourceApiKeyDraft() {
  sourceForm.api_keys = [...sourceApiKeyDraft.value]
  sourceApiKeysDialog.value = false
}

function openCreateSourceModel() {
  startCreateSourceModel()
}

function openEditSourceModel(item: AISourceModelItem) {
  selectSourceModel(item)
}

function requestRemoveSourceModel(item: AISourceModelItem) {
  pendingDeleteModel.value = {
    label: item.display_name || item.model_identifier,
    modelId: item.model_id,
  }
  modelDeleteDialog.value = true
}

async function confirmRemoveSourceModel() {
  if (!pendingDeleteModel.value) {
    return
  }
  const target = pendingDeleteModel.value
  modelDeleteDialog.value = false
  pendingDeleteModel.value = null
  await removeSourceModel(target.modelId)
}

function capabilityProvenanceSources(value: Record<string, unknown> | undefined) {
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

function workflowTone(status: 'error' | 'success' | 'warning'): BadgeVariants['variant'] {
  if (status === 'success') {
    return 'default'
  }
  if (status === 'error') {
    return 'destructive'
  }
  return 'secondary'
}

function sourceAdvancedLabel(field: SourceAdvancedField) {
  if (field === 'capability_metadata_json') {
    return t('ai.capabilityMetadata')
  }
  if (field === 'default_options_json') {
    return t('ai.defaultOptions')
  }
  return t('ai.capabilityProvenance')
}

function modelAdvancedLabel(field: ModelAdvancedField) {
  if (field === 'capability_metadata_json') {
    return t('ai.capabilityMetadata')
  }
  if (field === 'default_options_json') {
    return t('ai.defaultOptions')
  }
  return t('ai.capabilityProvenance')
}

function connectionIssueLabel(issue: string) {
  return t(`ai.connectionIssue.${issue}`)
}

function stringQuery(query: Record<string, unknown>) {
  const result: Record<string, string> = {}
  for (const [key, value] of Object.entries(query)) {
    if (typeof value === 'string' && value) {
      result[key] = value
    }
  }
  return result
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
  if (applyingRouteState) {
    return
  }
  syncRouteQuery()
}, { flush: 'sync' })
</script>

<template>
  <PageScaffold
    :embedded="embedded"
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.models')"
    :title="t('ai.modelsTitle')"
  >
    <div class="ai-model-local-toolbar">
      <ToggleGroup
        :aria-label="t('ai.sourceCapabilitySwitcherLabel')"
        class="ai-model-capability-switcher"
        :model-value="sourceCapabilityTab"
        size="sm"
        type="single"
        variant="outline"
        @update:model-value="handleCapabilityUpdate"
      >
        <ToggleGroupItem
          v-for="item in sourceCapabilityOptions"
          :key="item.value"
          :value="item.value"
        >
          {{ item.title }}
        </ToggleGroupItem>
      </ToggleGroup>
      <Button
        class="ai-model-local-toolbar__refresh"
        :disabled="loading"
        variant="secondary"
        @click="loadData"
      >
        <RefreshCw :class="{ 'animate-spin': loading }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </div>

    <LoadingSkeleton v-if="loading && loadingSources" rows="8" />

    <div v-else class="ai-model-page">
      <SplitPane class="ai-model-workbench" wide-sidebar>
        <template #sidebar>
          <Panel :title="t('ai.sourcesTitle')">
            <template #actions>
              <Button size="sm" @click="startCreateSource()">
                <Plus :size="15" />
                {{ t('ai.createSource') }}
              </Button>
            </template>

            <div class="ai-source-search">
              <Search :size="16" />
              <Input v-model="sourceSearch" :placeholder="t('common.search')" />
            </div>

            <SelectableList v-if="filteredSources.length > 0" class="ai-source-list">
              <SelectableListItem
                v-for="item in filteredSources"
                :key="item.source_id"
                :active="item.source_id === sourceForm.source_id"
                @click="selectSource(item)"
              >
                <div class="ai-source-list-item">
                  <div class="ai-source-list-item__icon">
                    <ServerCog :size="17" />
                  </div>
                  <div class="ai-source-list-item__body">
                    <strong>{{ item.name }}</strong>
                    <span>{{ item.api_base || t('common.none') }}</span>
                    <div>
                      <Badge :variant="item.enabled ? 'default' : 'secondary'">
                        {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
                      </Badge>
                      <Badge variant="outline">
                        {{ sourcePresetLabel(item.preset_type) }}
                      </Badge>
                    </div>
                  </div>
                </div>
              </SelectableListItem>
            </SelectableList>

            <EmptyState
              v-else
              :action-label="t('ai.setupAction.createProvider')"
              :icon="ServerCog"
              :text="t('ai.noSourcesHint')"
              :title="t('ai.noSources')"
              @action="startCreateSource()"
            />
          </Panel>
        </template>

        <div class="ai-model-workbench__main">
          <div
            class="ai-model-primary-grid"
            :class="{ 'ai-model-primary-grid--with-models': providerDetailMode !== 'empty' && sourceForm.source_id }"
          >
            <Panel
              :subtitle="providerDetailText"
              :title="providerDetailTitle"
            >
              <template #actions>
                <Badge
                  v-if="setupWorkflow.connectionIssues.length === 0 && sourceForm.source_id"
                  variant="default"
                >
                  {{ t('ai.setupStep.connection') }}
                </Badge>
                <Badge
                  v-for="issue in setupWorkflow.connectionIssues"
                  :key="issue"
                  variant="secondary"
                >
                  {{ connectionIssueLabel(issue) }}
                </Badge>
              </template>

              <EmptyState
                v-if="providerDetailMode === 'empty'"
                :action-label="t('ai.createSource')"
                :icon="ServerCog"
                :text="t('ai.sourceProviderEmptyText')"
                :title="t('ai.sourceProviderEmptyTitle')"
                @action="startCreateSource()"
              />

              <div v-else class="ai-provider-form">
                <div
                  v-if="isCreatingSource"
                  class="ai-source-protocol-grid"
                  :class="{ 'ai-source-protocol-grid--focused': modelFlowFocus.highlight === 'provider' }"
                >
                  <button
                    v-for="preset in sourcePresets"
                    :key="preset.preset_type"
                    :aria-pressed="sourceForm.preset_type === preset.preset_type"
                    class="ai-source-protocol"
                    :class="{ 'ai-source-protocol--active': sourceForm.preset_type === preset.preset_type }"
                    type="button"
                    @click="selectSourceProtocol(preset.preset_type)"
                  >
                    <span>{{ sourcePresetInitial(preset.preset_type) }}</span>
                    <strong>{{ preset.display_name }}</strong>
                    <small>{{ preset.description || t('ai.sourceProtocolDefaultHint') }}</small>
                  </button>
                </div>

                <div class="ai-form-grid">
                  <FormField
                    :error="displayedSourceErrors.name"
                    :helper="t('ai.sourceConfigNameHint')"
                    :label="t('ai.sourceName')"
                    required
                  >
                    <Input
                      v-model="sourceForm.name"
                      :aria-invalid="Boolean(displayedSourceErrors.name)"
                      :disabled="savingSource"
                      @blur="touchSourceField('name')"
                    />
                  </FormField>

                  <FormField
                    :error="displayedSourceErrors.preset_type"
                    :helper="t('ai.sourceConfigPresetHint')"
                    :label="t('ai.sourcePreset')"
                    required
                  >
                    <Select
                      v-model="sourceForm.preset_type"
                      :disabled="savingSource || isCreatingSource"
                      @update:model-value="() => touchSourceField('preset_type')"
                    >
                      <SelectTrigger>
                        <SelectValue :placeholder="t('ai.sourceProtocolNotSelected')" />
                      </SelectTrigger>
                        <SelectContent>
                        <SelectGroup>
                          <SelectItem
                            v-for="item in sourcePresetOptions"
                            :key="item.value"
                            :value="item.value"
                          >
                            {{ item.title }}
                          </SelectItem>
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </FormField>

                  <FormField
                    :helper="t('ai.sourceConfigApiBaseHint')"
                    :label="t('ai.sourceApiBase')"
                  >
                    <Input v-model="sourceForm.api_base" :disabled="savingSource" />
                  </FormField>

                  <FormField
                    :helper="t('ai.sourceConfigApiKeyHint')"
                    :label="t('ai.sourceApiKey')"
                  >
                    <form
                      autocomplete="off"
                      class="ai-api-key-row"
                      @submit.prevent
                    >
                      <input
                        autocomplete="username"
                        hidden
                        name="username"
                        readonly
                        type="text"
                        value="api-key"
                      >
                      <Input
                        v-model="sourcePrimaryApiKey"
                        autocomplete="off"
                        type="password"
                      />
                      <Button
                        :class="{ 'ai-highlight-button': modelFlowFocus.highlight === 'connection' }"
                        type="button"
                        variant="secondary"
                        @click="openSourceApiKeysEditor"
                      >
                        <KeyRound :size="15" />
                        {{ t('ai.sourceApiKeyManage') }}
                      </Button>
                    </form>
                    <div v-if="extraSourceApiKeys.length > 0" class="ai-inline-chips">
                      <Badge
                        v-for="(item, index) in extraSourceApiKeys"
                        :key="`${index}-${item}`"
                        variant="secondary"
                      >
                        {{ item }}
                        <button
                          :aria-label="t('common.delete')"
                          class="ai-chip-button"
                          type="button"
                          @click="removeExtraSourceApiKey(index)"
                        >
                          ×
                        </button>
                      </Badge>
                    </div>
                  </FormField>
                </div>

                <div class="ai-provider-switches">
                  <label>
                    <Switch v-model:checked="sourceForm.enabled" :disabled="savingSource" />
                    <span>{{ t('ai.sourceEnabled') }}</span>
                  </label>
                  <span v-if="providerSaveDisabledReason" class="ai-disabled-reason">
                    {{ providerSaveDisabledReason }}
                  </span>
                </div>

                <div v-if="workflowResults.provider" class="ai-workflow-result">
                  <Badge :variant="workflowTone(workflowResults.provider.status)">
                    {{ workflowResults.provider.message }}
                  </Badge>
                </div>

                <div class="ai-form-actions">
                  <Button variant="secondary" @click="sourceAdvancedDialog = true">
                    <Settings :size="15" />
                    {{ t('ai.sourceAdvancedConfigAction') }}
                  </Button>
                  <Button
                    v-if="sourceForm.source_id"
                    :disabled="deletingSource"
                    variant="destructive"
                    @click="removeSource"
                  >
                    <Trash2 :size="15" />
                    {{ t('common.delete') }}
                  </Button>
                  <Button :disabled="!canSaveSource" @click="saveSource">
                    {{ t('ai.saveSourceConfig') }}
                  </Button>
                </div>
              </div>
            </Panel>

            <Panel
              v-if="sourceForm.source_id"
              :title="t('ai.sourceModelsTitle')"
            >
              <template #actions>
                <Button
                  :class="{ 'ai-highlight-button': modelFlowFocus.highlight === 'fetch' }"
                  :disabled="!canFetchSourceModels"
                  size="sm"
                  variant="secondary"
                  @click="pullSourceModels"
                >
                  <RefreshCw :class="{ 'animate-spin': fetchingSourceModels }" :size="15" />
                  {{ t('ai.fetchModels') }}
                </Button>
                <Button :disabled="!sourceForm.source_id" size="sm" @click="openCreateSourceModel">
                  <Plus :size="15" />
                  {{ t('ai.customModel') }}
                </Button>
              </template>

              <div class="ai-model-toolbar">
                <div class="ai-source-search">
                  <Search :size="16" />
                  <Input v-model="sourceModelSearch" :placeholder="t('ai.modelSearch')" />
                </div>
                <span>{{ t('ai.availableModelsCount') }}: {{ importableSourceModels.length }}</span>
              </div>

              <div v-if="modelFetchDisabledReason" class="ai-disabled-reason">
                {{ modelFetchDisabledReason }}
              </div>
              <div v-if="workflowResults.discovery" class="ai-workflow-result">
                <Badge :variant="workflowTone(workflowResults.discovery.status)">
                  {{ workflowResults.discovery.message }}
                </Badge>
              </div>

              <LoadingSkeleton v-if="loadingSourceModels" rows="4" />

              <div v-else-if="unifiedSourceModels.length > 0" class="ai-source-model-list ai-source-model-list--compact">
                <article
                  v-for="item in unifiedSourceModels"
                  :key="item.key"
                  class="ai-source-model-row"
                  :class="{
                    'ai-source-model-row--active': item.kind === 'configured' && item.model_id === modelForm.model_id,
                    'ai-source-model-row--importable': item.kind === 'importable',
                    'ai-source-model-row--target': modelFlowFocus.highlight === 'import' && item.kind === 'importable',
                  }"
                  @click="item.kind === 'configured' ? openEditSourceModel(item) : undefined"
                >
                  <div class="ai-source-model-row__body">
                    <strong>{{ item.display_name }}</strong>
                    <span>{{ item.model_identifier }}</span>
                  </div>
                  <div class="ai-inline-chips">
                    <template v-if="item.kind === 'configured'">
                      <Badge :variant="item.enabled ? 'default' : 'secondary'">
                        {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
                      </Badge>
                      <Badge v-if="item.is_default" variant="outline">
                        {{ t('ai.modelDefault') }}
                      </Badge>
                    </template>
                    <Badge
                      v-for="source in capabilityProvenanceSources(item.capability_provenance)"
                      :key="`${item.key}-${source}`"
                      variant="secondary"
                    >
                      {{ source }}
                    </Badge>
                  </div>
                  <div class="ai-source-model-row__actions">
                    <template v-if="item.kind === 'configured'">
                      <Button size="icon" variant="ghost" @click.stop="openEditSourceModel(item)">
                        <Settings :size="15" />
                      </Button>
                      <Button
                        :disabled="!canTestModels"
                        size="icon"
                        variant="ghost"
                        @click.stop="testSourceModel(item.model_identifier)"
                      >
                        <FlaskConical
                          :class="{ 'animate-spin': testingModelIdentifier === item.model_identifier }"
                          :size="15"
                        />
                      </Button>
                      <Button
                        :disabled="deletingModelId === item.model_id"
                        size="icon"
                        variant="ghost"
                        @click.stop="requestRemoveSourceModel(item)"
                      >
                        <Trash2 :size="15" />
                      </Button>
                    </template>
                    <Button
                      v-else
                      :disabled="!!importingModelIdentifier && importingModelIdentifier !== item.model_identifier"
                      size="sm"
                      variant="secondary"
                      @click.stop="importSourceModelCatalogItem({
                        capability_metadata: item.capability_metadata,
                        capability_provenance: item.capability_provenance,
                        default_options: item.default_options,
                        id: item.model_identifier,
                        name: item.display_name,
                      } as AIModelCatalogItem)"
                    >
                      <Plus
                        :class="{ 'animate-spin': importingModelIdentifier === item.model_identifier }"
                        :size="15"
                      />
                      {{ t('ai.importModel') }}
                    </Button>
                  </div>
                </article>
              </div>

              <EmptyState
                v-else
                :action-label="t('ai.customModel')"
                :icon="Brain"
                :text="modelEmptyText"
                :title="t('ai.modelEmptyTitle')"
                @action="openCreateSourceModel"
              />
            </Panel>
          </div>

          <Panel v-if="sourceForm.source_id" :title="isCreatingModel ? t('ai.createModel') : t('ai.editModel')">
            <template #actions>
              <Button variant="secondary" @click="modelAdvancedDialog = true">
                <Settings :size="15" />
                {{ t('ai.modelAdvancedConfigAction') }}
              </Button>
            </template>
            <template v-if="sourceForm.source_id">
              <div
                class="ai-model-editor"
                :class="{ 'ai-model-editor--focused': modelFlowFocus.step === 'model' || modelFlowFocus.step === 'defaultModel' }"
              >
                <div class="ai-model-editor__header">
                  <div>
                    <strong>{{ isCreatingModel ? t('ai.createModel') : t('ai.editModel') }}</strong>
                    <p>{{ t(`ai.modelFlowStepHint.${modelFlowFocus.step}`) }}</p>
                  </div>
                </div>

                <div class="ai-form-grid">
                  <FormField
                    :error="displayedModelErrors.model_identifier"
                    :label="t('ai.modelIdentifier')"
                    required
                  >
                    <Input
                      v-model="modelForm.model_identifier"
                      :aria-invalid="Boolean(displayedModelErrors.model_identifier)"
                      :disabled="savingModel"
                      @blur="touchModelField('model_identifier')"
                    />
                  </FormField>
                  <FormField
                    :error="displayedModelErrors.display_name"
                    :label="t('ai.modelDisplayName')"
                    required
                  >
                    <Input
                      v-model="modelForm.display_name"
                      :aria-invalid="Boolean(displayedModelErrors.display_name)"
                      :disabled="savingModel"
                      @blur="touchModelField('display_name')"
                    />
                  </FormField>
                </div>

                <div class="ai-provider-switches">
                  <label>
                    <Switch v-model:checked="modelForm.enabled" :disabled="savingModel" />
                    <span>{{ t('ai.modelEnabled') }}</span>
                  </label>
                  <label>
                    <Switch v-model:checked="modelForm.is_default" :disabled="savingModel" />
                    <span>{{ t('ai.modelDefault') }}</span>
                  </label>
                </div>
                <div v-if="modelSaveDisabledReason" class="ai-disabled-reason">
                  {{ modelSaveDisabledReason }}
                </div>
                <div v-if="workflowResults.model" class="ai-workflow-result">
                  <Badge :variant="workflowTone(workflowResults.model.status)">
                    {{ workflowResults.model.message }}
                  </Badge>
                </div>
                <div class="ai-form-actions">
                  <Button :disabled="!canSaveModel" @click="saveSourceModel">
                    {{ t('common.save') }}
                  </Button>
                </div>
              </div>
            </template>
          </Panel>

          <Panel
            v-if="isChatCapability"
            :subtitle="t('ai.profileWorkflowHint')"
            :title="t('ai.modelProfiles')"
          >
            <template #actions>
              <Badge variant="secondary">
                {{ t('ai.modelProfiles') }}: {{ modelProfileCount }}
              </Badge>
              <Badge variant="secondary">
                {{ t('ai.scopeBindings') }}: {{ selectedModelBindingCount }}
              </Badge>
              <Button size="sm" @click="startCreateModelProfile">
                <Plus :size="15" />
                {{ t('ai.createModelProfile') }}
              </Button>
            </template>

            <EmptyState
              v-if="sourceModels.length === 0"
              :icon="CircleAlert"
              :text="t('ai.modelProfileRequiresModel')"
              :title="t('ai.profileEmptyTitle')"
            />

            <template v-else>
              <div v-if="filteredModelProfiles.length > 0" class="ai-profile-list">
                <button
                  v-for="item in filteredModelProfiles"
                  :key="item.profile_id"
                  class="ai-profile-row"
                  :class="{ 'ai-profile-row--active': item.profile_id === profileForm.profile_id }"
                  type="button"
                  @click="selectModelProfile(item as AIModelProfileItem)"
                >
                  <span>
                    <strong>{{ item.name }}</strong>
                    <small>{{ item.task_class }} · {{ item.priority }}</small>
                  </span>
                  <Badge :variant="item.enabled ? 'default' : 'secondary'">
                    {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
                  </Badge>
                </button>
              </div>
              <EmptyState
                v-else
                :action-label="t('ai.createModelProfile')"
                :icon="CheckCircle2"
                :text="t('ai.profileEmptyText')"
                :title="t('ai.profileEmptyTitle')"
                @action="startCreateModelProfile"
              />

              <div
                class="ai-profile-editor"
                :class="{ 'ai-profile-editor--focused': modelFlowFocus.step === 'profile' }"
              >
                <div class="ai-model-editor__header">
                  <strong>{{ isCreatingProfile ? t('ai.createModelProfile') : t('ai.editModel') }}</strong>
                </div>
                <div class="ai-form-grid">
                  <FormField
                    :error="displayedProfileErrors.name"
                    :label="t('ai.modelProfileName')"
                    required
                  >
                    <Input
                      v-model="profileForm.name"
                      :aria-invalid="Boolean(displayedProfileErrors.name)"
                      :disabled="savingProfile"
                      @blur="touchProfileField('name')"
                    />
                  </FormField>
                  <FormField
                    :error="displayedProfileErrors.model_id"
                    :label="t('ai.modelName')"
                    required
                  >
                    <Select
                      v-model="profileForm.model_id"
                      :disabled="savingProfile"
                      @update:model-value="() => touchProfileField('model_id')"
                    >
                      <SelectTrigger>
                        <SelectValue :placeholder="t('ai.modelName')" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectItem
                            v-for="item in profileModelOptions"
                            :key="item.value"
                            :value="item.value"
                          >
                            {{ item.title }}
                          </SelectItem>
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </FormField>
                  <FormField :label="t('ai.modelTaskClass')">
                    <Select v-model="profileForm.task_class" :disabled="savingProfile">
                      <SelectTrigger>
                        <SelectValue :placeholder="t('ai.modelTaskClass')" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectItem
                            v-for="item in taskClassOptions"
                            :key="item.value"
                            :value="item.value"
                          >
                            {{ item.title }}
                          </SelectItem>
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </FormField>
                  <FormField :label="t('ai.modelProfilePriority')">
                    <Input v-model="profileForm.priority" :disabled="savingProfile" type="number" />
                  </FormField>
                  <FormField :label="t('ai.modelProfileFallback')">
                    <Select
                      :model-value="profileForm.fallback_profile_id || '__none__'"
                      :disabled="savingProfile"
                      @update:model-value="value => {
                        profileForm.fallback_profile_id = value === '__none__' ? '' : String(value)
                      }"
                    >
                      <SelectTrigger>
                        <SelectValue :placeholder="t('common.none')" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectItem value="__none__">
                            {{ t('common.none') }}
                          </SelectItem>
                          <SelectItem
                            v-for="item in fallbackProfileOptions"
                            :key="item.value"
                            :value="item.value"
                          >
                            {{ item.title }}
                          </SelectItem>
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </FormField>
                  <label class="ai-switch-field">
                    <Switch v-model:checked="profileForm.enabled" :disabled="savingProfile" />
                    <span>{{ t('ai.modelProfileEnabled') }}</span>
                  </label>
                </div>
                <div v-if="profileSaveDisabledReason" class="ai-disabled-reason">
                  {{ profileSaveDisabledReason }}
                </div>
                <div v-if="workflowResults.profile" class="ai-workflow-result">
                  <Badge :variant="workflowTone(workflowResults.profile.status)">
                    {{ workflowResults.profile.message }}
                  </Badge>
                </div>
                <div class="ai-form-actions">
                  <Button :disabled="!canSaveProfile" @click="saveModelProfile">
                    {{ t('common.save') }}
                  </Button>
                </div>
              </div>
            </template>
          </Panel>

          <Panel
            v-if="setupWorkflow.selectedModel"
            :subtitle="t('ai.modelValidationHint', { model: setupWorkflow.selectedModel.display_name })"
            :title="t('ai.setupStep.validation')"
          >
            <template #actions>
              <Button
                :class="{ 'ai-highlight-button': modelFlowFocus.highlight === 'test' }"
                :disabled="!canTestModels"
                variant="secondary"
                @click="testSourceModel(setupWorkflow.selectedModel?.model_identifier || '')"
              >
                <FlaskConical
                  :class="{ 'animate-spin': testingModelIdentifier === setupWorkflow.selectedModel?.model_identifier }"
                  :size="15"
                />
                {{ t('ai.testModel') }}
              </Button>
            </template>
            <div v-if="modelTestDisabledReason" class="ai-disabled-reason">
              {{ modelTestDisabledReason }}
            </div>
            <div v-if="workflowResults.validation" class="ai-workflow-result">
              <Badge :variant="workflowTone(workflowResults.validation.status)">
                {{ workflowResults.validation.message }}
              </Badge>
              <pre v-if="workflowResults.validation.detail">{{ workflowResults.validation.detail }}</pre>
            </div>
          </Panel>
        </div>
      </SplitPane>
    </div>

    <Dialog v-model:open="sourceApiKeysDialog">
      <DialogContent class="ai-dialog-wide">
        <DialogHeader>
          <DialogTitle>{{ t('ai.sourceApiKeyManageTitle') }}</DialogTitle>
          <DialogDescription>{{ t('ai.sourceConfigApiKeyHint') }}</DialogDescription>
        </DialogHeader>
        <div class="ai-api-key-editor">
          <div class="ai-api-key-row">
            <Input
              v-model="sourceApiKeyDraftInput"
              :placeholder="t('ai.sourceApiKeyNew')"
              @keydown.enter.prevent="appendSourceApiKeyDraft"
            />
            <Button type="button" variant="secondary" @click="appendSourceApiKeyDraft">
              {{ t('ai.sourceApiKeyAdd') }}
            </Button>
          </div>
          <div class="ai-api-key-list">
            <div
              v-for="(item, index) in sourceApiKeyDraft"
              :key="`${index}-${item}`"
              class="ai-api-key-item"
            >
              <span>{{ item }}</span>
              <Button size="icon" variant="ghost" @click="removeSourceApiKeyDraft(index)">
                <Trash2 :size="15" />
              </Button>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" @click="sourceApiKeysDialog = false">
            {{ t('common.cancel') }}
          </Button>
          <Button @click="applySourceApiKeyDraft">
            {{ t('common.confirm') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="sourceAdvancedDialog">
      <DialogContent class="ai-dialog-wide">
        <DialogHeader>
          <DialogTitle>{{ t('ai.sourceAdvancedConfig') }}</DialogTitle>
          <DialogDescription>{{ t('ai.providerWorkflowHint') }}</DialogDescription>
        </DialogHeader>
        <div class="ai-form-grid">
          <FormField :label="t('ai.sourceAdapterKind')">
            <Input v-model="sourceForm.adapter_kind" :disabled="savingSource" />
          </FormField>
          <FormField :label="t('ai.sourceTimeoutSeconds')">
            <Input
              :model-value="sourceForm.timeout_seconds ?? ''"
              :disabled="savingSource"
              type="number"
              @update:model-value="value => {
                const nextValue = Number(value)
                sourceForm.timeout_seconds = Number.isFinite(nextValue) ? nextValue : null
              }"
            />
          </FormField>
          <FormField :label="t('ai.sourceProxy')">
            <Input v-model="sourceForm.proxy" :disabled="savingSource" />
          </FormField>
          <FormField v-if="sourceForm.capability_type === 'embedding'" :label="t('ai.sourceEmbeddingDimensions')">
            <Input
              :model-value="sourceForm.embedding_dimensions ?? ''"
              :disabled="savingSource"
              type="number"
              @update:model-value="value => {
                const nextValue = Number(value)
                sourceForm.embedding_dimensions = Number.isFinite(nextValue) ? nextValue : null
              }"
            />
          </FormField>
          <FormField v-if="sourceForm.capability_type === 'speech_to_text'" :label="t('ai.sourceSttLanguage')">
            <Input v-model="sourceForm.stt_language" :disabled="savingSource" />
          </FormField>
          <FormField v-if="sourceForm.capability_type === 'text_to_speech'" :label="t('ai.sourceTtsVoice')">
            <Input v-model="sourceForm.tts_voice" :disabled="savingSource" />
          </FormField>
          <FormField v-if="sourceForm.capability_type === 'text_to_speech'" :label="t('ai.sourceTtsFormat')">
            <Select v-model="sourceForm.tts_response_format" :disabled="savingSource">
              <SelectTrigger>
                <SelectValue :placeholder="t('ai.sourceTtsFormat')" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem
                    v-for="item in ttsResponseFormatOptions"
                    :key="item.value"
                    :value="item.value"
                  >
                    {{ item.title }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </FormField>
          <FormField v-if="sourceForm.capability_type === 'rerank'" :label="t('ai.sourceRerankApiSuffix')">
            <Input v-model="sourceForm.rerank_api_suffix" :disabled="savingSource" />
          </FormField>
          <FormField v-if="sourceForm.capability_type === 'rerank'" :label="t('ai.sourceRerankTopN')">
            <Input
              :model-value="sourceForm.rerank_top_n ?? ''"
              :disabled="savingSource"
              type="number"
              @update:model-value="value => {
                const nextValue = Number(value)
                sourceForm.rerank_top_n = Number.isFinite(nextValue) ? nextValue : null
              }"
            />
          </FormField>
          <FormField
            v-for="field in (['capability_metadata_json', 'default_options_json', 'capability_provenance_json'] as SourceAdvancedField[])"
            :key="field"
            class="ai-form-field-wide"
            :label="sourceAdvancedLabel(field)"
          >
            <Textarea
              v-model="sourceForm[field]"
              class="ai-json-editor"
              :disabled="savingSource"
              spellcheck="false"
            />
          </FormField>
        </div>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="modelAdvancedDialog">
      <DialogContent class="ai-dialog-wide">
        <DialogHeader>
          <DialogTitle>{{ t('ai.modelAdvancedConfigAction') }}</DialogTitle>
          <DialogDescription>{{ t('ai.modelDiscoveryWorkflowHint') }}</DialogDescription>
        </DialogHeader>
        <div class="ai-form-grid">
          <FormField
            v-for="field in (['capability_metadata_json', 'default_options_json', 'capability_provenance_json'] as ModelAdvancedField[])"
            :key="field"
            class="ai-form-field-wide"
            :label="modelAdvancedLabel(field)"
          >
            <Textarea
              v-model="modelForm[field]"
              class="ai-json-editor"
              :disabled="savingModel"
              spellcheck="false"
            />
          </FormField>
        </div>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="modelDeleteDialog">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ t('ai.deleteModelConfirmTitle') }}</DialogTitle>
          <DialogDescription>
            {{ t('ai.deleteModelConfirmText', { name: pendingDeleteModel?.label || t('common.none') }) }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" @click="modelDeleteDialog = false">
            {{ t('common.cancel') }}
          </Button>
          <Button variant="destructive" @click="confirmRemoveSourceModel">
            {{ t('common.confirm') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </PageScaffold>
</template>
