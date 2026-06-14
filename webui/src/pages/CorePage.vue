<script setup lang="ts">
import type { DriverConfigItem } from '@/api/core'
import type { RawSettingsResponse } from '@/api/settings'
import type { SettingField } from '@/utils/settingsEditor'
import {
  AlertCircle,
  Cable,
  CheckCircle2,
  Code2,
  Download,
  Eye,
  FileCog,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Save,
  Search,
  SlidersHorizontal,
  Trash2,
  Wrench,
} from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import {
  getCoreSettings,
  getCoreSettingsRaw,
  getDriverConfig,
  updateCoreSettings,
  updateCoreSettingsRaw,
  validateCoreSettingsRaw,
} from '@/api/core'
import {
  EmptyState,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
  RawSettingsEditor,
  StatusBadge,
  TaskDialog,
} from '@/components/management'
import type { WorkbenchMetricItem, WorkbenchTone } from '@/components/management'
import { SettingsFieldEditor } from '@/components/settings'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { AdapterSelectionItem } from '@/api/adapters'
import { useAdapterManagement } from '@/composables/useAdapterManagement'
import { useAdapterSelection } from '@/composables/useAdapterSelection'
import { usePluginSettingsDialog } from '@/composables/usePluginSettingsDialog'
import { useRawTomlValidation } from '@/composables/useRawTomlValidation'
import { useSettingsEditor } from '@/composables/useSettingsEditor'
import { useNoticeStore } from '@/stores/notice'
import { useRestartStore } from '@/stores/restart'
import {
  buildRevertValues,
  buildSettingsPreviewItems,
  displayChoiceTitle,
  displayFieldValue,
} from '@/utils/settingsEditor'

type CoreTab = 'core' | 'adapters' | 'drivers'

// ═══════════════════════════════════════════════════════════════════════
// COMPOSABLES & REACTIVE STATE
// ═══════════════════════════════════════════════════════════════════════

const { t } = useI18n()
const noticeStore = useNoticeStore()
const restartStore = useRestartStore()
const loading = ref(false)
const errorMessage = ref('')
const activeTab = ref<CoreTab>('core')
const previewDialogVisible = ref(false)
const coreRawDialogVisible = ref(false)
const coreRawPreviewVisible = ref(false)
const coreRawText = ref('')
const coreRawInitialText = ref('')
const coreRawLoading = ref(false)
const coreRawSaving = ref(false)
const coreRawErrorMessage = ref('')
const adapterConfigDialogVisible = ref(false)
const adapterPreviewVisible = ref(false)
const driverBuiltin = ref<DriverConfigItem[]>([])

const coreEditor = useSettingsEditor({
  load: getCoreSettings,
  save: payload => updateCoreSettings(payload),
  messages: {
    invalidJson: t('plugins.settingsInvalidJson'),
    loadFailed: t('plugins.settingsLoadFailed'),
    saveFailed: t('plugins.settingsSaveFailed'),
    saveSuccess: t('plugins.settingsSaved'),
  },
  afterSave: ({ previousState, values, clear }) => {
    restartStore.markPending({
      id: 'core:settings',
      scope: 'core',
      summary: t('restart.pendingCoreSettings'),
      undo: {
        kind: 'core-settings',
        values: buildRevertValues(previousState.fields, values, clear),
      },
    })
  },
})

const adapterManager = useAdapterManagement({
  noticeStore,
  restartStore,
  t: (key, params) => t(key, params || {}),
})

const adapterSelection = useAdapterSelection({
  noticeStore,
  restartStore,
  t: (key, params) => t(key, params || {}),
})

const adapterSettings = usePluginSettingsDialog({
  noticeStore,
  restartStore,
  t: (key, params) => t(key, params || {}),
})

const corePreviewItems = computed(() =>
  buildSettingsPreviewItems(
    coreEditor.fields.value,
    coreEditor.form.value,
    coreEditor.draftClears.value,
    t('plugins.settingsInvalidJson'),
  ),
)
const adapterPreviewNextModules = computed(() =>
  adapterManager.previewItems.value[1]?.value ?? [],
)
const hasPendingCoreRawChanges = computed(() =>
  coreRawText.value !== coreRawInitialText.value,
)
const loadedAdapterCount = computed(() =>
  adapterSelection.summary.value.loaded,
)
const unavailableAdapterCount = computed(() =>
  adapterSelection.summary.value.unavailable,
)
const activeDriverCount = computed(() =>
  driverBuiltin.value.filter(item => item.is_active).length,
)

// ═══════════════════════════════════════════════════════════════════════
// DERIVED / COMPUTED
// ═══════════════════════════════════════════════════════════════════════

const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    key: 'settings',
    label: t('core.settingsMetric'),
    value: coreEditor.fields.value.length || '...',
    icon: FileCog,
    tone: 'info',
  },
  {
    key: 'adapter-runtime',
    label: t('core.adapterOverviewRuntimeTitle'),
    value: t('core.adapterOverviewRuntimeValue', {
      loaded: loadedAdapterCount.value,
      total: adapterSelection.summary.value.enabled,
    }),
    icon: Cable,
    tone: unavailableAdapterCount.value > 0 ? 'warning' : 'success',
  },
  {
    key: 'drivers',
    label: t('plugins.driverCount'),
    value: `${activeDriverCount.value}/${driverBuiltin.value.length}`,
    icon: Wrench,
  },
])
const hasAdapterDiagnostics = computed(() =>
  adapterManager.hasPendingChanges.value
  || adapterManager.blankRowCount.value > 0
  || adapterManager.duplicateModules.value.length > 0
  || adapterManager.unchangedModules.value.length > 0,
)
const adapterDiagnosticsSummary = computed(() => {
  if (!adapterManager.hasPendingChanges.value && adapterManager.normalizationNotes.value.length === 0) {
    return t('core.adapterDiagnosticsClean')
  }
  return t('core.adapterDiagnosticsSummary', {
    added: adapterManager.addedModules.value.length,
    removed: adapterManager.removedModules.value.length,
    total: adapterPreviewNextModules.value.length,
  })
})
const {
  validateNow: validateCoreRawNow,
  validationColumn: coreRawValidationColumn,
  validationLine: coreRawValidationLine,
  validationMessage: coreRawValidationMessage,
  validationPending: coreRawValidationPending,
} = useRawTomlValidation({
  text: coreRawText,
  initialText: coreRawInitialText,
  fallbackMessage: t('plugins.settingsRawValidateFailed'),
  validate: async text => (await validateCoreSettingsRaw({ text })).data,
})

// ═══════════════════════════════════════════════════════════════════════
// DATA LOADING & REFRESH
// ═══════════════════════════════════════════════════════════════════════

async function refreshCorePage() {
  loading.value = true
  errorMessage.value = ''
  try {
    await Promise.all([
      coreEditor.reload(),
      adapterManager.reload(),
      adapterSelection.reload(),
      loadDriverManagement(),
    ])
  } finally {
    loading.value = false
  }
}

async function loadDriverManagement() {
  try {
    const response = await getDriverConfig()
    driverBuiltin.value = response.data.builtin
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('core.loadFailed'))
  }
}

// ═══════════════════════════════════════════════════════════════════════
// CORE SETTINGS: DIALOG / RAW / PREVIEW / SAVE
// ═══════════════════════════════════════════════════════════════════════

function openCoreSettingsPreview() {
  if (corePreviewItems.value.length === 0) {
    return
  }
  previewDialogVisible.value = true
}

function applyCoreRawState(nextState: RawSettingsResponse) {
  coreRawText.value = nextState.text
  coreRawInitialText.value = nextState.text
}

async function loadCoreRawSettings() {
  coreRawLoading.value = true
  coreRawErrorMessage.value = ''
  try {
    const response = await getCoreSettingsRaw()
    applyCoreRawState(response.data)
  } catch (error) {
    coreRawErrorMessage.value = getErrorMessage(
      error,
      t('plugins.settingsRawLoadFailed'),
    )
  } finally {
    coreRawLoading.value = false
  }
}

function openCoreRawDialog() {
  coreRawDialogVisible.value = true
  void loadCoreRawSettings()
}

async function openCoreRawPreview() {
  if (!hasPendingCoreRawChanges.value) {
    return
  }
  if (!await validateCoreRawNow()) {
    return
  }
  coreRawPreviewVisible.value = true
}

async function confirmCoreRawSave() {
  if (!hasPendingCoreRawChanges.value) {
    return
  }
  coreRawSaving.value = true
  coreRawErrorMessage.value = ''
  const previousText = coreRawInitialText.value
  try {
    const rawResponse = await updateCoreSettingsRaw({ text: coreRawText.value })
    const settingsResponse = await getCoreSettings()
    applyCoreRawState(rawResponse.data)
    coreEditor.applyState(settingsResponse.data)
    restartStore.markPending({
      id: 'core:raw',
      scope: 'core',
      summary: t('restart.pendingCoreRaw'),
      undo: {
        kind: 'core-raw',
        text: previousText,
      },
    })
    noticeStore.show(t('plugins.settingsRawSaved'), 'success')
    coreRawPreviewVisible.value = false
  } catch (error) {
    const message = getErrorMessage(error, t('plugins.settingsRawSaveFailed'))
    coreRawErrorMessage.value = message
    noticeStore.show(message, 'error')
  } finally {
    coreRawSaving.value = false
  }
}

async function confirmCoreSettingsSave() {
  const saved = await coreEditor.submit()
  if (saved) {
    previewDialogVisible.value = false
  }
}

// ═══════════════════════════════════════════════════════════════════════
// ADAPTER SELECTION: POPUP, CANDIDATE, EXPERT CONFIG
// ═══════════════════════════════════════════════════════════════════════

function openAdapterExpertConfig() {
  adapterConfigDialogVisible.value = true
}

function openAdapterPreview() {
  if (!adapterManager.hasPendingChanges.value) {
    return
  }
  adapterPreviewVisible.value = true
}

async function confirmAdapterPreviewSave() {
  const saved = await adapterManager.save()
  if (saved) {
    adapterPreviewVisible.value = false
    adapterConfigDialogVisible.value = false
  }
}

function clearCoreField(field: SettingField) {
  coreEditor.clearField(field)
}

// ═══════════════════════════════════════════════════════════════════════
// DISPLAY HELPERS (sources, tones, labels)
// ═══════════════════════════════════════════════════════════════════════

function fieldSourceLabel(source: string) {
  const map: Record<string, string> = {
    default: t('plugins.settingsValueSourceDefault'),
    env: t('plugins.settingsValueSourceEnv'),
    plugin_section: t('plugins.settingsValueSourcePlugin'),
  }
  return map[source] || source
}

function formatFieldChoices(field: SettingField) {
  const normalized = field.choices.map(choice => displayChoiceTitle(choice)).filter(Boolean)
  if (normalized.length <= 4) {
    return normalized.join(' / ')
  }
  return `${normalized.slice(0, 4).join(' / ')} +${normalized.length - 4}`
}

function formatModuleList(modules: string[]) {
  return modules.length > 0 ? modules.join('\n') : t('common.none')
}

function adapterTone(item: Pick<AdapterSelectionItem, 'is_loaded' | 'is_importable'>): WorkbenchTone {
  if (!item.is_importable) {
    return 'warning'
  }
  return item.is_loaded ? 'success' : 'default'
}

function adapterStateLabel(item: AdapterSelectionItem) {
  const map: Record<AdapterSelectionItem['state'], string> = {
    available: t('core.adapterStateAvailable'),
    installed: t('core.adapterStateInstalled'),
    enabled_loaded: t('core.adapterStateEnabledLoaded'),
    enabled_pending_restart: t('core.adapterStateEnabledPendingRestart'),
    unavailable: t('core.adapterStateUnavailable'),
  }
  return map[item.state] || item.state
}

function adapterStateTone(item: AdapterSelectionItem): WorkbenchTone {
  if (item.state === 'unavailable') {
    return 'warning'
  }
  if (item.state === 'enabled_loaded') {
    return 'success'
  }
  if (item.state === 'enabled_pending_restart' || item.state === 'installed') {
    return 'info'
  }
  return 'default'
}

function adapterPrimaryActionLabel(item: AdapterSelectionItem | null) {
  if (!item) {
    return t('core.adapterSelectionChoose')
  }
  if (item.is_enabled) {
    return item.is_loaded
      ? t('core.adapterSelectionAlreadyEnabled')
      : t('core.adapterSelectionEnabledPendingRestart')
  }
  if (item.is_installed) {
    return t('core.adapterSelectionEnable')
  }
  return t('core.adapterSelectionInstallAndEnable')
}

function adapterPrimaryActionDisabled(item: AdapterSelectionItem | null) {
  return !item || item.is_enabled || adapterSelection.actionLocked.value
}

function adapterExternalUrl(item: AdapterSelectionItem | null) {
  const url = item?.homepage || item?.project_link || ''
  return url.startsWith('http://') || url.startsWith('https://') ? url : ''
}

function openAdapterSettings(item: AdapterSelectionItem) {
  if (!item.is_configurable) {
    noticeStore.show(t('core.adapterSelectionNoEditableConfig'), 'info')
    return
  }
  void adapterSettings.openSettings({
    module_name: item.module_name,
    kind: 'adapter',
    access_mode: 'default_allow',
    name: item.display_name,
    description: item.description,
    homepage: item.homepage,
    source: item.source_name || 'adapter',
    is_global_enabled: true,
    is_protected: false,
    protected_reason: null,
    plugin_type: 'adapter',
    author: null,
    version: null,
    is_loaded: item.is_loaded,
    is_explicit: item.is_enabled,
    is_dependency: false,
    is_pending_uninstall: false,
    can_edit_config: item.is_configurable,
    can_view_readme: false,
    can_enable_disable: false,
    can_uninstall: false,
    can_package_update: item.can_update,
    child_plugins: [],
    required_plugins: [],
    dependent_plugins: [],
    installed_package: item.installed_package || item.package_name,
    installed_module_names: item.installed_module_names,
  })
}

function openAdapterSettingsPreview() {
  void adapterSettings.openPluginSettingsPreview()
}

function openAdapterRawPreview() {
  void adapterSettings.openPluginRawPreview()
}

function toggleAdapterUnenabledOnly(value: boolean | 'indeterminate') {
  adapterSelection.unenabledOnly.value = value === true
  void adapterSelection.loadPopupSelection()
}

function reloadOpenAdapterRawSettings() {
  const moduleName = adapterSettings.settingsPlugin.value?.module_name
  if (moduleName) {
    void adapterSettings.loadPluginRawSettings(moduleName)
  }
}

function driverTone(item: DriverConfigItem): WorkbenchTone {
  return item.is_active ? 'success' : 'warning'
}

function driverStatusText(item: DriverConfigItem) {
  return item.is_active ? t('plugins.driverActive') : t('plugins.driverRegisteredOnly')
}

// ═══════════════════════════════════════════════════════════════════════
// LIFECYCLE
// ═══════════════════════════════════════════════════════════════════════

onMounted(() => {
  void refreshCorePage()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :kicker="t('layout.systemSection')"
    :subtitle="t('core.description')"
    :title="t('core.title')"
  >
    <template #actions>
      <!-- ====== SECTION: Toolbar ====== -->
      <Button :disabled="loading" variant="secondary" @click="refreshCorePage">
        <RefreshCw :class="{ 'animate-spin': loading }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <!-- ====== SECTION: Metrics ====== -->

    <MetricStrip :items="metrics" />

    <!-- ====== SECTION: Tabs (Core / Adapters / Drivers) ====== -->

    <Tabs v-model="activeTab" class="core-workbench">
      <TabsList class="core-tabs-list">
        <TabsTrigger value="core">
          <FileCog :size="15" />
          {{ t('core.coreTab') }}
        </TabsTrigger>
        <TabsTrigger value="adapters">
          <Cable :size="15" />
          {{ t('core.adaptersTab') }}
        </TabsTrigger>
        <TabsTrigger value="drivers">
          <Wrench :size="15" />
          {{ t('core.driversTab') }}
        </TabsTrigger>
      </TabsList>

      <!-- ====== TAB SECTION: Core Settings Editor ====== -->

      <TabsContent value="core">
        <Panel
          :subtitle="t('core.settingsDescription')"
          :title="t('core.coreTab')"
        >
          <template #actions>
            <Button
              :disabled="coreRawLoading || coreRawSaving"
              variant="secondary"
              @click="openCoreRawDialog"
            >
              <Code2 :size="16" />
              {{ t('plugins.settingsAdvancedAction') }}
            </Button>
            <Button
              :disabled="!coreEditor.hasPendingChanges.value || coreEditor.saving.value"
              @click="openCoreSettingsPreview"
            >
              <Save :size="16" />
              {{ t('plugins.settingsSave') }}
            </Button>
          </template>

          <Alert v-if="coreEditor.errorMessage.value" variant="destructive">
            <AlertCircle :size="16" />
            <AlertDescription>{{ coreEditor.errorMessage.value }}</AlertDescription>
          </Alert>

          <LoadingSkeleton v-if="coreEditor.loading.value" rows="8" />
          <EmptyState
            v-else-if="coreEditor.fields.value.length === 0"
            :title="t('core.noSettings')"
            :text="t('core.noSettingsText')"
          />

          <div v-else class="settings-list-panel">
            <article
              v-for="field in coreEditor.fields.value"
              :key="field.key"
              class="settings-list-row settings-list-row--compact"
            >
              <div class="settings-list-row__main">
                <div class="settings-list-row__info">
                  <div class="settings-list-row__label">
                    {{ field.label || field.key }}
                  </div>
                  <div v-if="field.help" class="settings-list-row__description">
                    {{ field.help }}
                  </div>
                  <div class="settings-list-row__status">
                    <StatusBadge
                      v-if="field.has_local_override"
                      :label="t('plugins.settingsLocalShort')"
                      tone="info"
                    />
                    <StatusBadge
                      v-if="!field.editable"
                      :label="t('plugins.settingsReadonly')"
                      tone="warning"
                    />
                  </div>
                  <div class="settings-list-row__value-summary">
                    {{ t('plugins.settingsCurrent') }}:
                    {{ displayFieldValue(field.current_value) }}
                  </div>
                </div>

                <div class="settings-list-row__control">
                  <div class="settings-list-row__actions">
                    <Button
                      v-if="coreEditor.hasFieldPending(field)"
                      size="sm"
                      variant="ghost"
                      @click="coreEditor.cancelField(field)"
                    >
                      {{ t('common.cancel') }}
                    </Button>
                    <Button
                      v-if="field.has_local_override"
                      size="sm"
                      variant="ghost"
                      @click="clearCoreField(field)"
                    >
                      {{ t('plugins.settingsClear') }}
                    </Button>
                  </div>

                  <SettingsFieldEditor
                    :model-value="coreEditor.form.value[field.key]"
                    :array-hint="t('plugins.settingsArrayHint')"
                    :editable="field.editable"
                    :field="field"
                    :json-hint="t('plugins.settingsJsonHint')"
                    @update:model-value="value => coreEditor.updateFieldValue(field, value)"
                  />
                </div>
              </div>

              <details class="settings-list-row__advanced">
                <summary class="settings-list-row__advanced-summary">
                  <span class="settings-list-row__advanced-label settings-list-row__advanced-label--closed">
                    {{ t('core.showAdvancedDetails') }}
                  </span>
                  <span class="settings-list-row__advanced-label settings-list-row__advanced-label--open">
                    {{ t('core.hideAdvancedDetails') }}
                  </span>
                </summary>
                <div class="settings-list-row__meta">
                  <span>{{ t('plugins.settingsType') }}: {{ field.type }}</span>
                  <span>{{ t('plugins.settingsValueSource') }}: {{ fieldSourceLabel(field.value_source) }}</span>
                  <span v-if="field.choices.length > 0">
                    {{ t('plugins.settingsChoices') }}: {{ formatFieldChoices(field) }}
                  </span>
                  <span>{{ t('plugins.settingsCurrent') }}: {{ displayFieldValue(field.current_value) }}</span>
                  <span v-if="field.has_local_override">
                    {{ t('plugins.settingsLocal') }}: {{ displayFieldValue(field.local_value) }}
                  </span>
                </div>
              </details>
            </article>
          </div>
        </Panel>
      </TabsContent>

      <!-- ====== TAB SECTION: Adapters Overview & List ====== -->

      <TabsContent value="adapters">
        <Panel
          :subtitle="t('core.adapterConfigDescription')"
          :title="t('core.adaptersTab')"
        >
          <template #actions>
            <Badge variant="secondary">
              {{ t('core.adapterSelectionEnabledCount', { count: adapterSelection.summary.value.enabled }) }}
            </Badge>
            <Button @click="adapterSelection.openPopup">
              <Plus data-icon="inline-start" />
              {{ t('core.adapterSelectionAdd') }}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button variant="outline" size="icon">
                  <MoreHorizontal data-icon="inline-start" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuGroup>
                  <DropdownMenuItem @click="openAdapterExpertConfig">
                    <SlidersHorizontal data-icon="inline-start" />
                    {{ t('core.adapterSelectionExpertEdit') }}
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </template>

          <Alert v-if="adapterSelection.errorMessage.value" variant="destructive">
            <AlertCircle :size="16" />
            <AlertDescription>{{ adapterSelection.errorMessage.value }}</AlertDescription>
          </Alert>

          <LoadingSkeleton v-if="adapterSelection.loading.value" rows="5" />

          <div v-else class="adapter-overview">
            <div class="adapter-selection-summary">
              <div class="adapter-selection-summary__item">
                <CheckCircle2 :size="18" />
                <div>
                  <div class="adapter-selection-summary__label">
                    {{ t('core.adapterSelectionEnabled') }}
                  </div>
                  <strong>{{ adapterSelection.summary.value.enabled }}</strong>
                </div>
              </div>

              <div class="adapter-selection-summary__item">
                <Cable :size="18" />
                <div>
                  <div class="adapter-selection-summary__label">
                    {{ t('core.adapterOverviewRuntimeTitle') }}
                  </div>
                  <strong>{{ adapterSelection.summary.value.loaded }}</strong>
                </div>
              </div>

              <div
                class="adapter-selection-summary__item"
                :class="{ 'adapter-selection-summary__item--warning': adapterSelection.summary.value.unavailable > 0 }"
              >
                <AlertCircle :size="18" />
                <div>
                  <div class="adapter-selection-summary__label">
                    {{ t('core.adapterStateUnavailable') }}
                  </div>
                  <strong>{{ adapterSelection.summary.value.unavailable }}</strong>
                </div>
              </div>

              <div class="adapter-selection-summary__item">
                <RefreshCw :size="18" />
                <div>
                  <div class="adapter-selection-summary__label">
                    {{ t('core.adapterSelectionRestartRequired') }}
                  </div>
                  <strong>{{ adapterSelection.summary.value.restart_required }}</strong>
                </div>
              </div>
            </div>

            <section
              v-if="adapterSelection.enabledAdapters.value.length > 0"
              class="adapter-status-list"
              :aria-label="t('core.adapterOverviewListTitle')"
            >
              <div class="adapter-status-list__header">
                <div>
                  <div class="adapter-status-list__title">
                    {{ t('core.adapterSelectionEnabledAdapters') }}
                  </div>
                  <div class="adapter-status-list__description">
                    {{ t('core.adapterSelectionEnabledAdaptersDescription') }}
                  </div>
                </div>
              </div>

              <article
                v-for="item in adapterSelection.enabledAdapters.value"
                :key="item.module_name"
                class="adapter-status-row"
              >
                <div class="adapter-status-row__signal" :class="`workbench-tone--${adapterTone(item)}`">
                  <CheckCircle2 v-if="item.is_loaded" :size="18" />
                  <AlertCircle v-else :size="18" />
                </div>
                <div class="adapter-status-row__main">
                  <div class="adapter-status-row__title-line">
                    <h2 class="adapter-status-row__title">
                      {{ item.display_name }}
                    </h2>
                    <div class="adapter-status-row__chips">
                      <StatusBadge :label="adapterStateLabel(item)" :tone="adapterStateTone(item)" />
                      <StatusBadge
                        v-if="item.is_configurable"
                        :label="t('core.adapterSelectionConfigurable')"
                        tone="info"
                      />
                    </div>
                  </div>
                  <div class="adapter-status-row__module">
                    {{ item.package_name || item.installed_package || item.module_name }}
                  </div>
                  <div class="adapter-status-row__summary">
                    {{ item.description || item.module_name }}
                  </div>
                </div>

                <div class="adapter-status-row__actions">
                  <Button
                    :disabled="!item.is_configurable"
                    size="sm"
                    variant="secondary"
                    @click="openAdapterSettings(item)"
                  >
                    <SlidersHorizontal data-icon="inline-start" />
                    {{ item.is_configurable ? t('plugins.settings') : t('core.adapterSelectionNoConfig') }}
                  </Button>
                  <Button
                    :disabled="adapterSelection.actionLocked.value"
                    size="sm"
                    variant="outline"
                    @click="adapterSelection.disableAdapter(item)"
                  >
                    {{ t('core.adapterSelectionDisable') }}
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger as-child>
                      <Button size="icon" variant="ghost">
                        <MoreHorizontal data-icon="inline-start" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuGroup>
                        <DropdownMenuItem
                          :disabled="!item.can_update || adapterSelection.actionLocked.value"
                          @click="adapterSelection.updateAdapter(item)"
                        >
                          <RefreshCw data-icon="inline-start" />
                          {{ t('adapterStore.update') }}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          :disabled="adapterSelection.actionLocked.value || (!item.installed_package && !item.package_name)"
                          @click="adapterSelection.uninstallAdapter(item)"
                        >
                          <Trash2 data-icon="inline-start" />
                          {{ t('adapterStore.uninstall') }}
                        </DropdownMenuItem>
                      </DropdownMenuGroup>
                      <DropdownMenuSeparator />
                      <DropdownMenuGroup>
                        <DropdownMenuItem @click="openAdapterExpertConfig">
                          <Code2 data-icon="inline-start" />
                          {{ t('core.adapterSelectionExpertEdit') }}
                        </DropdownMenuItem>
                      </DropdownMenuGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <details class="adapter-status-row__details">
                  <summary>{{ t('core.adapterSelectionTechnicalDetails') }}</summary>
                  <div>
                    <span>{{ t('core.adapterModuleLabel') }}: {{ item.module_name }}</span>
                    <span>{{ t('adapterStore.packageName') }}: {{ item.package_name || item.installed_package || t('common.none') }}</span>
                  </div>
                </details>
              </article>
            </section>

            <EmptyState
              v-else
              :text="t('core.adapterSelectionEmptyText')"
              :title="t('core.adapterSelectionEmptyTitle')"
            >
              <template #actions>
                <Button @click="adapterSelection.openPopup">
                  <Plus data-icon="inline-start" />
                  {{ t('core.adapterSelectionAdd') }}
                </Button>
                <Button variant="ghost" @click="openAdapterExpertConfig">
                  <Code2 data-icon="inline-start" />
                  {{ t('core.adapterSelectionExpertEdit') }}
                </Button>
              </template>
            </EmptyState>
          </div>
        </Panel>
      </TabsContent>

      <!-- ====== TAB SECTION: Drivers ====== -->

      <TabsContent value="drivers">
        <Panel
          :subtitle="t('core.driverConfigDescription')"
          :title="t('core.driversTab')"
        >
          <EmptyState
            v-if="driverBuiltin.length === 0"
            :title="t('plugins.emptyDriverBuiltin')"
          />

          <div v-else class="driver-grid">
            <div v-for="driverItem in driverBuiltin" :key="driverItem.name" class="driver-row">
              <div>
                <div class="driver-row__name">
                  {{ driverItem.name }}
                </div>
                <div class="driver-row__state">
                  {{ driverStatusText(driverItem) }}
                </div>
              </div>
              <StatusBadge :label="driverStatusText(driverItem)" :tone="driverTone(driverItem)" />
            </div>
          </div>
        </Panel>
      </TabsContent>
    </Tabs>

    <!-- ====== DIALOG: Settings Preview ====== -->

    <Dialog v-model:open="previewDialogVisible">
      <DialogContent class="settings-preview-dialog">
        <DialogHeader>
          <DialogTitle>{{ t('plugins.previewChangesTitle') }}</DialogTitle>
          <DialogDescription>{{ t('plugins.settingsRestartHint') }}</DialogDescription>
        </DialogHeader>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{{ t('plugins.settingsField') }}</TableHead>
              <TableHead>{{ t('plugins.previewCurrent') }}</TableHead>
              <TableHead>{{ t('plugins.previewNext') }}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="item in corePreviewItems" :key="item.key">
              <TableCell class="settings-preview-dialog__key">
                {{ item.key }}
              </TableCell>
              <TableCell>{{ item.current }}</TableCell>
              <TableCell>{{ item.next }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>

        <DialogFooter>
          <Button variant="ghost" @click="previewDialogVisible = false">
            {{ t('common.cancel') }}
          </Button>
          <Button :disabled="coreEditor.saving.value" @click="confirmCoreSettingsSave">
            <Save :size="16" />
            {{ t('plugins.confirmSave') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ====== DIALOG: Raw Settings Editor ====== -->

    <Dialog v-model:open="coreRawDialogVisible">
      <DialogContent class="core-raw-settings-dialog">
        <DialogHeader>
          <DialogTitle>{{ t('plugins.settingsAdvancedAction') }}</DialogTitle>
          <DialogDescription>{{ t('plugins.settingsAdvancedDescription') }}</DialogDescription>
        </DialogHeader>

        <RawSettingsEditor
          v-model="coreRawText"
          :description="t('plugins.settingsAdvancedDescription')"
          :dirty="hasPendingCoreRawChanges"
          :error-message="coreRawErrorMessage"
          :loading="coreRawLoading"
          :reload-label="t('common.refresh')"
          :save-label="t('plugins.settingsSave')"
          :saving="coreRawSaving"
          :validation-error-column="coreRawValidationColumn"
          :validation-error-line="coreRawValidationLine"
          :validation-error-message="coreRawValidationMessage"
          :validation-pending="coreRawValidationPending"
          @reload="loadCoreRawSettings"
          @save="openCoreRawPreview"
        />

        <DialogFooter>
          <Button variant="ghost" @click="coreRawDialogVisible = false">
            {{ t('common.close') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ====== DIALOG: Raw Settings Preview ====== -->

    <Dialog v-model:open="coreRawPreviewVisible">
      <DialogContent class="settings-preview-dialog">
        <DialogHeader>
          <DialogTitle>{{ t('plugins.previewRawTitle') }}</DialogTitle>
          <DialogDescription>{{ t('plugins.settingsRestartHint') }}</DialogDescription>
        </DialogHeader>

        <div class="settings-raw-preview-grid">
          <div class="settings-raw-preview-block">
            <div class="settings-raw-preview-block__label">
              {{ t('plugins.previewCurrent') }}
            </div>
            <pre>{{ coreRawInitialText }}</pre>
          </div>
          <div class="settings-raw-preview-block">
            <div class="settings-raw-preview-block__label">
              {{ t('plugins.previewNext') }}
            </div>
            <pre>{{ coreRawText }}</pre>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" @click="coreRawPreviewVisible = false">
            {{ t('common.cancel') }}
          </Button>
          <Button :disabled="coreRawSaving" @click="confirmCoreRawSave">
            <Save :size="16" />
            {{ t('plugins.confirmSave') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ====== DIALOG: Adapter Selection Popup ====== -->

    <Dialog v-model:open="adapterSelection.popupVisible.value">
      <DialogContent class="adapter-selection-dialog">
        <DialogHeader>
          <DialogTitle>{{ t('core.adapterSelectionAdd') }}</DialogTitle>
          <DialogDescription>{{ t('core.adapterSelectionDescription') }}</DialogDescription>
        </DialogHeader>

        <Alert v-if="adapterSelection.popupErrorMessage.value" variant="destructive">
          <AlertCircle data-icon="inline-start" />
          <AlertDescription>{{ adapterSelection.popupErrorMessage.value }}</AlertDescription>
        </Alert>

        <div class="adapter-selection-toolbar">
          <div class="adapter-selection-search">
            <Search :size="16" />
            <Input
              v-model="adapterSelection.search.value"
              :placeholder="t('core.adapterSelectionSearch')"
              @input="adapterSelection.schedulePopupReload"
            />
          </div>
          <label class="adapter-selection-filter">
            <Checkbox
              :checked="adapterSelection.unenabledOnly.value"
              @update:checked="toggleAdapterUnenabledOnly"
            />
            <span>{{ t('core.adapterSelectionOnlyUnenabled') }}</span>
          </label>
        </div>

        <LoadingSkeleton v-if="adapterSelection.popupLoading.value" rows="8" />

        <div v-else class="adapter-selection-layout">
          <section class="adapter-selection-list" :aria-label="t('core.adapterSelectionCandidates')">
            <button
              v-for="item in adapterSelection.candidates.value"
              :key="`${item.source_id || 'local'}:${item.module_name}`"
              class="adapter-selection-option"
              :class="{
                'adapter-selection-option--active':
                  adapterSelection.selectedCandidateKey.value
                  === `${item.source_id || 'local'}:${item.module_name}`,
              }"
              type="button"
              @click="adapterSelection.selectCandidate(item)"
            >
              <span class="adapter-selection-option__title">{{ item.display_name }}</span>
              <span class="adapter-selection-option__module">{{ item.package_name || item.module_name }}</span>
              <span class="adapter-selection-option__chips">
                <StatusBadge :label="adapterStateLabel(item)" :tone="adapterStateTone(item)" />
                <Badge v-if="item.is_official" variant="outline">{{ t('adapterStore.official') }}</Badge>
              </span>
            </button>

            <EmptyState
              v-if="adapterSelection.candidates.value.length === 0"
              compact
              :text="t('core.adapterSelectionNoResultsText')"
              :title="t('core.adapterSelectionNoResults')"
            />
          </section>

          <aside class="adapter-selection-detail">
            <template v-if="adapterSelection.selectedCandidate.value">
              <div class="adapter-selection-detail__header">
                <div>
                  <div class="adapter-selection-detail__eyebrow">
                    {{ adapterSelection.selectedCandidate.value.source_name || t('core.adaptersTab') }}
                  </div>
                  <h3>{{ adapterSelection.selectedCandidate.value.display_name }}</h3>
                </div>
                <StatusBadge
                  :label="adapterStateLabel(adapterSelection.selectedCandidate.value)"
                  :tone="adapterStateTone(adapterSelection.selectedCandidate.value)"
                />
              </div>

              <p class="adapter-selection-detail__description">
                {{ adapterSelection.selectedCandidate.value.description || adapterSelection.selectedCandidate.value.module_name }}
              </p>

              <div class="adapter-selection-detail__meta">
                <span>{{ t('core.adapterModuleLabel') }}</span>
                <code>{{ adapterSelection.selectedCandidate.value.module_name }}</code>
                <span>{{ t('adapterStore.packageName') }}</span>
                <code>{{ adapterSelection.selectedCandidate.value.package_name || t('common.none') }}</code>
              </div>

              <div class="adapter-selection-detail__tags">
                <Badge
                  v-for="tag in adapterSelection.selectedCandidate.value.tags.slice(0, 6)"
                  :key="tag"
                  variant="secondary"
                >
                  {{ tag }}
                </Badge>
              </div>

              <div class="adapter-selection-detail__actions">
                <Button
                  :disabled="adapterPrimaryActionDisabled(adapterSelection.selectedCandidate.value)"
                  @click="adapterSelection.applySelectedCandidate"
                >
                  <Download data-icon="inline-start" />
                  {{ adapterPrimaryActionLabel(adapterSelection.selectedCandidate.value) }}
                </Button>
                <Button
                  v-if="adapterExternalUrl(adapterSelection.selectedCandidate.value)"
                  as="a"
                  :href="adapterExternalUrl(adapterSelection.selectedCandidate.value)"
                  rel="noreferrer"
                  target="_blank"
                  variant="outline"
                >
                  {{ t('adapterStore.openProject') }}
                </Button>
              </div>
            </template>

            <EmptyState
              v-else
              compact
              cause="selection-required"
              :title="t('core.adapterSelectionChoose')"
            />
          </aside>
        </div>

        <section class="adapter-selection-manual">
          <button
            class="adapter-selection-manual__toggle"
            type="button"
            @click="adapterSelection.manualExpanded.value = !adapterSelection.manualExpanded.value"
          >
            {{ t('core.adapterSelectionManualToggle') }}
          </button>

          <div v-if="adapterSelection.manualExpanded.value" class="adapter-selection-manual__form">
            <div class="adapter-selection-manual__field">
              <Label for="adapter-manual-requirement">{{ t('adapterStore.manualRequirement') }}</Label>
              <Input
                id="adapter-manual-requirement"
                v-model="adapterSelection.manualRequirement.value"
                :placeholder="t('adapterStore.manualRequirementPlaceholder')"
              />
            </div>
            <div class="adapter-selection-manual__field">
              <Label for="adapter-manual-module">{{ t('adapterStore.manualModule') }}</Label>
              <Input
                id="adapter-manual-module"
                v-model="adapterSelection.manualModuleName.value"
                :placeholder="t('adapterStore.manualModulePlaceholder')"
              />
            </div>
            <Button
              :disabled="!adapterSelection.canSubmitManualInstall.value || adapterSelection.actionLocked.value"
              variant="secondary"
              @click="adapterSelection.installManual"
            >
              <Download data-icon="inline-start" />
              {{ t('adapterStore.install') }}
            </Button>
          </div>
        </section>

        <DialogFooter>
          <Button variant="ghost" @click="adapterSelection.closePopup">
            {{ t('common.close') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ====== DIALOG: Adapter Expert Config ====== -->

    <Dialog v-model:open="adapterConfigDialogVisible">
      <DialogContent class="adapter-config-dialog">
        <DialogHeader>
          <DialogTitle>{{ t('core.adapterSelectionExpertEdit') }}</DialogTitle>
          <DialogDescription>{{ t('core.adapterModuleHelper') }}</DialogDescription>
        </DialogHeader>

        <Alert
          v-if="adapterManager.hasPendingChanges.value || adapterManager.normalizationNotes.value.length > 0"
          class="adapter-diagnostic-alert"
        >
          <Eye :size="16" />
          <AlertTitle>{{ adapterDiagnosticsSummary }}</AlertTitle>
          <AlertDescription>
            <span v-for="note in adapterManager.normalizationNotes.value" :key="note">
              {{ note }}
            </span>
          </AlertDescription>
        </Alert>

        <div class="adapter-panel__rows">
          <section
            v-for="row in adapterManager.draftRows.value"
            :key="row.id"
            class="adapter-row"
          >
            <div class="adapter-row__field">
              <Label :for="row.id">{{ t('core.adapterModuleLabel') }}</Label>
              <Input
                :id="row.id"
                v-model="row.value"
                :placeholder="t('core.adapterModulePlaceholder')"
              />
              <p v-if="adapterManager.rowStatusSummary(row.value)" class="adapter-row__hint">
                {{ adapterManager.rowStatusSummary(row.value) }}
              </p>
            </div>

            <Button size="icon" variant="ghost" @click="adapterManager.removeDraftRow(row.id)">
              <Trash2 :size="16" />
            </Button>
          </section>
        </div>

        <Button class="adapter-add-row" variant="ghost" @click="adapterManager.addDraftRow">
          <Plus :size="16" />
          {{ t('core.addAdapterModule') }}
        </Button>

        <div v-if="hasAdapterDiagnostics" class="adapter-diagnostics">
          <div class="adapter-diagnostics__group">
            <div class="adapter-diagnostics__label">{{ t('core.adapterPreviewNext') }}</div>
            <div class="adapter-diagnostics__value">{{ formatModuleList(adapterPreviewNextModules) }}</div>
          </div>
          <div v-if="adapterManager.addedModules.value.length > 0" class="adapter-diagnostics__group">
            <div class="adapter-diagnostics__label">{{ t('core.adapterPreviewAdded') }}</div>
            <div class="adapter-diagnostics__value">{{ formatModuleList(adapterManager.addedModules.value) }}</div>
          </div>
          <div v-if="adapterManager.removedModules.value.length > 0" class="adapter-diagnostics__group">
            <div class="adapter-diagnostics__label">{{ t('core.adapterPreviewRemoved') }}</div>
            <div class="adapter-diagnostics__value">{{ formatModuleList(adapterManager.removedModules.value) }}</div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" @click="adapterConfigDialogVisible = false">
            {{ t('common.close') }}
          </Button>
          <Button
            :disabled="!adapterManager.hasPendingChanges.value"
            @click="openAdapterPreview"
          >
            <Save :size="16" />
            {{ t('common.save') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ====== DIALOG: Adapter Preview ====== -->

    <Dialog v-model:open="adapterPreviewVisible">
      <DialogContent class="adapter-preview-dialog">
        <DialogHeader>
          <DialogTitle>{{ t('core.adapterPreviewTitle') }}</DialogTitle>
          <DialogDescription>{{ t('core.adapterRestartRequired') }}</DialogDescription>
        </DialogHeader>

        <div class="adapter-preview-grid">
          <div
            v-for="item in adapterManager.previewItems.value"
            :key="item.key"
            class="adapter-preview-block"
          >
            <div class="adapter-preview-block__label">{{ item.key }}</div>
            <pre class="adapter-preview-block__code">{{ formatModuleList(item.value) }}</pre>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" @click="adapterPreviewVisible = false">
            {{ t('common.cancel') }}
          </Button>
          <Button :disabled="adapterManager.saving.value" @click="confirmAdapterPreviewSave">
            <Save :size="16" />
            {{ t('plugins.confirmSave') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ====== DIALOG: Adapter Settings ====== -->

    <Dialog v-model:open="adapterSettings.settingsDialogVisible.value">
      <DialogContent class="plugin-settings-dialog">
        <DialogHeader>
          <DialogTitle>
            {{
              t('plugins.settingsTitle', {
                name: adapterSettings.settingsPlugin.value?.name
                  || adapterSettings.settingsPlugin.value?.module_name
                  || '',
              })
            }}
          </DialogTitle>
          <DialogDescription>{{ adapterSettings.settingsPlugin.value?.module_name }}</DialogDescription>
        </DialogHeader>

        <Alert v-if="adapterSettings.settingsErrorMessage.value" variant="destructive">
          <AlertCircle data-icon="inline-start" />
          <AlertDescription>{{ adapterSettings.settingsErrorMessage.value }}</AlertDescription>
        </Alert>

        <LoadingSkeleton v-if="adapterSettings.settingsDialogLoading.value" rows="7" />

        <Tabs
          v-else
          v-model="adapterSettings.settingsEditorMode.value"
          class="plugin-settings-tabs"
        >
          <div class="plugin-settings-tabs__bar">
            <TabsList>
              <TabsTrigger value="basic">
                <FileCog data-icon="inline-start" />
                {{ t('plugins.settingsBasicTab') }}
              </TabsTrigger>
              <TabsTrigger value="advanced">
                <Code2 data-icon="inline-start" />
                {{ t('plugins.settingsAdvancedTab') }}
              </TabsTrigger>
            </TabsList>

            <Button
              v-if="adapterSettings.settingsEditorMode.value === 'basic'"
              :disabled="!adapterSettings.hasPendingPluginChanges.value || adapterSettings.settingsSaving.value"
              size="sm"
              @click="openAdapterSettingsPreview"
            >
              <Save data-icon="inline-start" />
              {{ t('plugins.settingsSave') }}
            </Button>
          </div>

          <TabsContent value="basic" class="plugin-settings-tab-content">
            <EmptyState
              v-if="!adapterSettings.settingsState.value?.has_config_model
                || adapterSettings.settingsFields.value.length === 0"
              :title="t('core.adapterSelectionNoEditableConfig')"
            />

            <div v-else class="settings-list-panel plugin-settings-list">
              <article
                v-for="field in adapterSettings.settingsFields.value"
                :key="field.key"
                class="settings-list-row"
              >
                <div class="settings-list-row__main">
                  <div class="settings-list-row__info">
                    <div class="settings-list-row__label">
                      {{ field.label || field.key }}
                    </div>
                    <div v-if="field.help" class="settings-list-row__description">
                      {{ field.help }}
                    </div>
                    <div class="settings-list-row__status">
                      <StatusBadge
                        v-if="field.has_local_override"
                        :label="t('plugins.settingsLocalShort')"
                        tone="info"
                      />
                      <StatusBadge
                        v-if="!field.editable"
                        :label="t('plugins.settingsReadonly')"
                        tone="warning"
                      />
                    </div>
                    <div class="settings-list-row__value-summary">
                      {{ t('plugins.settingsCurrent') }}:
                      {{ adapterSettings.displayFieldValue(field.current_value) }}
                    </div>
                  </div>

                  <div class="settings-list-row__control">
                    <div class="settings-list-row__actions">
                      <Button
                        v-if="adapterSettings.pluginEditor.hasFieldPending(field)"
                        size="sm"
                        variant="ghost"
                        @click="adapterSettings.pluginEditor.cancelField(field)"
                      >
                        {{ t('common.cancel') }}
                      </Button>
                      <Button
                        v-if="field.has_local_override"
                        size="sm"
                        variant="ghost"
                        @click="adapterSettings.clearPluginField(field)"
                      >
                        {{ t('plugins.settingsClear') }}
                      </Button>
                    </div>

                    <SettingsFieldEditor
                      :model-value="adapterSettings.settingsForm.value[field.key]"
                      :array-hint="t('plugins.settingsArrayHint')"
                      :editable="field.editable"
                      :field="field"
                      :json-hint="t('plugins.settingsJsonHint')"
                      @update:model-value="value => adapterSettings.pluginEditor.updateFieldValue(field, value)"
                    />
                  </div>
                </div>
              </article>
            </div>
          </TabsContent>

          <TabsContent value="advanced" class="plugin-settings-tab-content">
            <RawSettingsEditor
              v-model="adapterSettings.settingsRawText.value"
              :description="t('plugins.settingsAdvancedDescription')"
              :dirty="adapterSettings.hasPendingPluginRawChanges.value"
              :error-message="adapterSettings.settingsRawErrorMessage.value"
              :loading="adapterSettings.settingsRawLoading.value"
              :reload-label="t('common.refresh')"
              :save-label="t('plugins.settingsSave')"
              :saving="adapterSettings.settingsRawSaving.value"
              :validation-error-column="adapterSettings.pluginRawValidationColumn.value"
              :validation-error-line="adapterSettings.pluginRawValidationLine.value"
              :validation-error-message="adapterSettings.pluginRawValidationMessage.value"
              :validation-pending="adapterSettings.pluginRawValidationPending.value"
              @reload="reloadOpenAdapterRawSettings"
              @save="openAdapterRawPreview"
            />
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button variant="ghost" @click="adapterSettings.closeSettingsDialog">
            {{ t('common.close') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ====== DIALOG: Adapter Settings Preview ====== -->

    <Dialog v-model:open="adapterSettings.previewDialogVisible.value">
      <DialogContent class="settings-preview-dialog">
        <DialogHeader>
          <DialogTitle>{{ adapterSettings.previewTitle.value }}</DialogTitle>
          <DialogDescription>{{ t('plugins.settingsRestartHint') }}</DialogDescription>
        </DialogHeader>

        <Table v-if="adapterSettings.previewMode.value === 'basic'">
          <TableHeader>
            <TableRow>
              <TableHead>{{ t('plugins.settingsField') }}</TableHead>
              <TableHead>{{ t('plugins.previewCurrent') }}</TableHead>
              <TableHead>{{ t('plugins.previewNext') }}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="item in adapterSettings.previewItems.value"
              :key="item.key"
            >
              <TableCell class="settings-preview-dialog__key">
                {{ item.key }}
              </TableCell>
              <TableCell>{{ item.current }}</TableCell>
              <TableCell>{{ item.next }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>

        <div v-else class="settings-raw-preview-grid">
          <div class="settings-raw-preview-block">
            <div class="settings-raw-preview-block__label">
              {{ t('plugins.previewCurrent') }}
            </div>
            <pre>{{ adapterSettings.previewCurrentText.value }}</pre>
          </div>
          <div class="settings-raw-preview-block">
            <div class="settings-raw-preview-block__label">
              {{ t('plugins.previewNext') }}
            </div>
            <pre>{{ adapterSettings.previewNextText.value }}</pre>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" @click="adapterSettings.previewDialogVisible.value = false">
            {{ t('common.cancel') }}
          </Button>
          <Button :disabled="adapterSettings.previewSaving.value" @click="adapterSettings.confirmPreviewSave">
            <Save data-icon="inline-start" />
            {{ t('plugins.confirmSave') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ====== SECTION: Adapter Task Dialog ====== -->

    <TaskDialog
      v-model="adapterSelection.taskDialogVisible.value"
      :binding-value="adapterSelection.activeTask.value?.binding_value"
      :close-label="t('common.close')"
      :current-phase="adapterSelection.activeTask.value?.current_phase"
      :current-phase-label="adapterSelection.activeTask.value?.current_phase_label"
      :diagnostics="adapterSelection.activeTask.value?.diagnostics || []"
      :loading="adapterSelection.taskIsRunning.value"
      :logs="adapterSelection.activeTask.value?.logs || ''"
      :operation="adapterSelection.activeTask.value?.operation"
      :queue-position="adapterSelection.activeTask.value?.queue_position"
      :raw-status="adapterSelection.activeTask.value?.status"
      :requirement="adapterSelection.activeTask.value?.requirement"
      :resource-kind="adapterSelection.activeTask.value?.resource_kind"
      :restart-required="adapterSelection.activeTask.value?.restart_required"
      :retry-label="adapterSelection.canRetryTask.value ? t('taskDialog.retry') : ''"
      :status="adapterSelection.taskStatusLabel.value"
      :status-tone="adapterSelection.taskStatusTone.value"
      :steps="adapterSelection.activeTask.value?.steps || []"
      :title="adapterSelection.activeTask.value?.title || t('adapterStore.installRunning')"
      :waiting-text="t('adapterStore.taskWaiting')"
      @retry="adapterSelection.retryActiveTask"
    />
  </PageScaffold>
</template>
