<script setup lang="ts">
import type {
  PluginInstallAction,
  PluginInstallResolution,
  PluginInstallSource,
  PluginStoreItem,
  PluginStoreSource,
  PluginStoreTask,
  PluginTogglePreview,
  PluginWorkbenchItem,
  PluginWorkbenchResponse,
} from '@/api/plugins'
import type { WorkbenchMetricItem, WorkbenchTone } from '@/components/management'
import {
  AlertCircle,
  Boxes,
  Code2,
  Eye,
  FileCog,
  FileText,
  Info,
  PackagePlus,
  Puzzle,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  UploadCloud,
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import {
  checkPluginUpdates,
  confirmPluginInstall,
  getPluginInstallTask,
  getPluginStoreItems,
  getPluginStoreSources,
  getPluginTogglePreview,
  getPluginWorkbench,
  resolvePluginInstallSource,
  uninstallPlugin,
  updateInstalledPlugin,
  updatePlugin,
} from '@/api/plugins'
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
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
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
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { usePluginReadmeDialog } from '@/composables/usePluginReadmeDialog'
import { usePluginSettingsDialog } from '@/composables/usePluginSettingsDialog'
import { useNoticeStore } from '@/stores/notice'
import { useRestartStore } from '@/stores/restart'
import {
  pluginProjectUrl,
  pluginSourceLabel,
  pluginSourceTone,
} from '@/utils/pluginDisplay'

type PluginFilter = 'all' | 'enabled' | 'disabled' | 'attention'
type InstallMode = 'store_item' | 'requirement' | 'local_path'

const { t } = useI18n()
const noticeStore = useNoticeStore()
const restartStore = useRestartStore()

const workbench = ref<PluginWorkbenchResponse | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const searchQuery = ref('')
const filter = ref<PluginFilter>('all')
const pendingModule = ref('')
const checkingUpdates = ref(false)

const toggleConfirmVisible = ref(false)
const toggleConfirmLoading = ref(false)
const toggleConfirmItem = ref<PluginWorkbenchItem | null>(null)
const toggleConfirmPreview = ref<PluginTogglePreview | null>(null)
const toggleConfirmNextValue = ref(false)

const installDialogVisible = ref(false)
const installMode = ref<InstallMode>('requirement')
const installSourceValue = ref('')
const installStoreSources = ref<PluginStoreSource[]>([])
const installStoreItems = ref<PluginStoreItem[]>([])
const installStoreLoading = ref(false)
const installStoreSourceId = ref('')
const installStoreItemId = ref('')
const installStoreSearch = ref('')
const installResolution = ref<PluginInstallResolution | null>(null)
const installResolving = ref(false)
const installSubmitting = ref(false)
const installManualModule = ref('')
const installSelectedModule = ref('')
const installTaskDialogVisible = ref(false)
const installTask = ref<PluginStoreTask | null>(null)
let installTaskPollTimer: number | null = null

const detailDialogVisible = ref(false)
const detailItem = ref<PluginWorkbenchItem | null>(null)

const uninstallConfirmVisible = ref(false)
const uninstallConfirmItem = ref<PluginWorkbenchItem | null>(null)
const uninstallRemoveConfig = ref(false)
const uninstallingModule = ref('')

const packageTaskDialogVisible = ref(false)
const packageTask = ref<PluginStoreTask | null>(null)
const packageTaskModule = ref('')
let packageTaskPollTimer: number | null = null

const pluginSettings = usePluginSettingsDialog({
  noticeStore,
  restartStore,
  t: (key, params) => t(key, params || {}),
})
const pluginReadme = usePluginReadmeDialog((key, params) => t(key, params || {}))

const plugins = computed(() => workbench.value?.plugins || [])
const summary = computed(() => workbench.value?.summary)
const maintenance = computed(() => workbench.value?.maintenance)

const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    key: 'total',
    label: t('dashboard.plugins'),
    value: summary.value?.total || 0,
    icon: Puzzle,
    tone: 'info',
  },
  {
    key: 'enabled',
    label: t('plugins.enabled'),
    value: summary.value?.enabled || 0,
    icon: Boxes,
    tone: 'success',
  },
  {
    key: 'blocked',
    label: t('plugins.stateExecutionBlocked'),
    value: summary.value?.blocked || 0,
    icon: SlidersHorizontal,
    tone: (summary.value?.blocked || 0) > 0 ? 'warning' : 'default',
  },
  {
    key: 'protected',
    label: t('plugins.protected'),
    value: summary.value?.protected || 0,
    icon: ShieldCheck,
    tone: 'warning',
  },
])

const filterOptions = computed(() => [
  { label: t('common.all'), value: 'all' },
  { label: t('ai.enabled'), value: 'enabled' },
  { label: t('ai.disabled'), value: 'disabled' },
  { label: t('plugins.needsAttention'), value: 'attention' },
])

const visiblePlugins = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return plugins.value
    .filter(item => {
      if (filter.value === 'enabled') {
        return item.policy.enabled
      }
      if (filter.value === 'disabled') {
        return !item.policy.enabled
      }
      if (filter.value === 'attention') {
        return item.effective_state !== 'active'
          || item.startup.requires_restart_to_apply_fully
          || item.is_pending_uninstall
      }
      return true
    })
    .filter(item => {
      if (!query) {
        return true
      }
      return [
        item.display_name,
        item.module_name,
        item.description,
        item.author,
        item.version,
        item.installed_package,
      ].some(value => String(value || '').toLowerCase().includes(query))
    })
})

const toggleConfirmTitle = computed(() =>
  toggleConfirmNextValue.value
    ? t('plugins.enableConfirmTitle')
    : t('plugins.disableConfirmTitle'),
)
const toggleConfirmSummary = computed(() => {
  if (toggleConfirmPreview.value?.blocked_reason) {
    return toggleConfirmPreview.value.blocked_reason
  }
  if (toggleConfirmPreview.value?.summary) {
    return toggleConfirmPreview.value.summary
  }
  return toggleConfirmNextValue.value
    ? t('plugins.enableRuntimeSummary')
    : t('plugins.disableRuntimeSummary')
})
const toggleConfirmAllowed = computed(() =>
  Boolean(toggleConfirmPreview.value?.allowed),
)
const toggleConfirmDependencies = computed(() => {
  const preview = toggleConfirmPreview.value
  if (!preview) {
    return []
  }
  return toggleConfirmNextValue.value
    ? [...preview.requires_enable, ...preview.missing_dependencies]
    : [...preview.requires_disable, ...preview.protected_dependents]
})

const selectedStoreItem = computed(() =>
  installStoreItems.value.find(item => item.plugin_id === installStoreItemId.value)
  || null,
)
const installSource = computed<PluginInstallSource>(() =>
  installMode.value === 'store_item'
    ? {
        kind: 'store_item',
        source_id: installStoreSourceId.value,
        item_id: installStoreItemId.value,
      }
    : {
        kind: installMode.value,
        value: installSourceValue.value.trim(),
      },
)
const installResolutionCandidates = computed(() =>
  installResolution.value?.candidates || [],
)
const installNeedsManualModule = computed(() =>
  installResolution.value?.status === 'unresolved',
)
const installNeedsCandidateChoice = computed(() =>
  installResolution.value?.status === 'ambiguous',
)
const installAction = computed<PluginInstallAction | null>(() => {
  const resolution = installResolution.value
  if (!resolution) {
    return null
  }
  if (resolution.default_action) {
    return resolution.default_action
  }
  if (installNeedsCandidateChoice.value && installSelectedModule.value) {
    return {
      kind: 'install_package',
      requirement: installMode.value === 'store_item'
        ? selectedStoreItem.value?.package_name || ''
        : installSourceValue.value.trim(),
      module_name: installSelectedModule.value,
    }
  }
  if (installNeedsManualModule.value && installManualModule.value.trim()) {
    return installMode.value === 'local_path'
      ? {
          kind: 'register_local_module',
          module_name: installManualModule.value.trim(),
          path: installSourceValue.value.trim(),
        }
      : {
          kind: 'install_package',
          requirement: installSourceValue.value.trim(),
          module_name: installManualModule.value.trim(),
        }
  }
  return null
})
const canConfirmInstall = computed(() =>
  Boolean(installResolution.value && installAction.value && !installSubmitting.value),
)
const installTaskRunning = computed(() =>
  installTask.value?.status === 'pending'
  || installTask.value?.status === 'queued'
  || installTask.value?.status === 'running',
)
const packageTaskRunning = computed(() =>
  packageTask.value?.status === 'pending'
  || packageTask.value?.status === 'queued'
  || packageTask.value?.status === 'running',
)
const canResolveInstall = computed(() =>
  installMode.value === 'store_item'
    ? Boolean(installStoreSourceId.value && installStoreItemId.value)
    : Boolean(installSourceValue.value.trim()),
)

async function loadWorkbench() {
  loading.value = true
  errorMessage.value = ''
  try {
    workbench.value = (await getPluginWorkbench()).data
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('plugins.loadFailed'))
  } finally {
    loading.value = false
  }
}

function pluginLabel(moduleName: string) {
  const match = plugins.value.find(item => item.module_name === moduleName)
  return match?.display_name || match?.name || match?.module_name || moduleName
}

function stateLabel(item: PluginWorkbenchItem) {
  const map: Record<string, string> = {
    active: t('plugins.stateActive'),
    execution_blocked: t('plugins.stateExecutionBlocked'),
    disabled: t('plugins.stateDisabled'),
    not_loaded: t('plugins.stateNotLoaded'),
    pending_uninstall: t('plugins.pendingUninstall'),
  }
  return map[item.effective_state] || item.effective_state
}

function stateTone(item: PluginWorkbenchItem): WorkbenchTone {
  if (item.effective_state === 'active') {
    return 'success'
  }
  if (item.effective_state === 'pending_uninstall') {
    return 'warning'
  }
  if (item.effective_state === 'execution_blocked' || item.effective_state === 'disabled') {
    return 'warning'
  }
  return 'default'
}

function restartHint(item: PluginWorkbenchItem) {
  if (item.effective_state === 'execution_blocked') {
    return t('plugins.disabledLoadedHint')
  }
  if (item.effective_state === 'disabled') {
    return t('plugins.disabledStartupHint')
  }
  if (item.effective_state === 'not_loaded') {
    return t('plugins.notLoadedHint')
  }
  if (item.is_pending_uninstall) {
    return t('plugins.pendingUninstallHint')
  }
  if (item.startup.requires_restart_to_apply_fully) {
    return t('plugins.restartRequiredHint')
  }
  return ''
}

function openInstallDialog() {
  installMode.value = 'requirement'
  installSourceValue.value = ''
  installStoreSources.value = []
  installStoreItems.value = []
  installStoreSourceId.value = ''
  installStoreItemId.value = ''
  installStoreSearch.value = ''
  installResolution.value = null
  installManualModule.value = ''
  installSelectedModule.value = ''
  installDialogVisible.value = true
}

async function resolveInstall() {
  if (!canResolveInstall.value) {
    return
  }
  installResolving.value = true
  installResolution.value = null
  installSelectedModule.value = ''
  installManualModule.value = ''
  try {
    const response = await resolvePluginInstallSource({
      source: installSource.value,
    })
    installResolution.value = response.data
    if (response.data.candidates.length === 1) {
      installSelectedModule.value = response.data.candidates[0].module_name
    }
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('plugins.installResolveFailed')), 'error')
  } finally {
    installResolving.value = false
  }
}

async function loadInstallStoreSources() {
  installStoreLoading.value = true
  try {
    const sources = (await getPluginStoreSources()).data
    installStoreSources.value = sources.filter(source => source.enabled)
    installStoreSourceId.value ||= installStoreSources.value[0]?.source_id || ''
    await loadInstallStoreItems()
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('plugins.installStoreLoadFailed')), 'error')
  } finally {
    installStoreLoading.value = false
  }
}

async function loadInstallStoreItems() {
  if (!installStoreSourceId.value) {
    installStoreItems.value = []
    installStoreItemId.value = ''
    return
  }
  installStoreLoading.value = true
  try {
    const response = await getPluginStoreItems({
      source: installStoreSourceId.value,
      search: installStoreSearch.value.trim() || undefined,
      uninstalled_only: true,
      per_page: 20,
    })
    installStoreItems.value = response.data.items
    if (!installStoreItems.value.some(item => item.plugin_id === installStoreItemId.value)) {
      installStoreItemId.value = installStoreItems.value[0]?.plugin_id || ''
    }
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('plugins.installStoreLoadFailed')), 'error')
  } finally {
    installStoreLoading.value = false
  }
}

async function confirmInstallAction() {
  if (!installAction.value) {
    return
  }
  installSubmitting.value = true
  try {
    const response = await confirmPluginInstall({
      source: installSource.value,
      action: installAction.value,
    })
    installTask.value = response.data
    installDialogVisible.value = false
    installTaskDialogVisible.value = true
    startInstallTaskPolling(response.data.task_id)
    if (response.data.restart_required) {
      restartStore.markPending({
        id: `plugin-install:${response.data.binding_value || response.data.task_id}`,
        scope: 'plugins',
        summary: t('plugins.manualInstallRestartPending', {
          name: response.data.binding_value || response.data.requirement || '',
        }),
        undo: response.data.requirement && response.data.binding_value
          ? {
              kind: 'plugin-install',
              packageName: response.data.requirement,
              moduleName: response.data.binding_value,
            }
          : undefined,
      })
    }
    await loadWorkbench()
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('plugins.manualInstallFailed')), 'error')
  } finally {
    installSubmitting.value = false
  }
}

function startInstallTaskPolling(taskId: string) {
  if (installTaskPollTimer !== null) {
    window.clearInterval(installTaskPollTimer)
  }
  installTaskPollTimer = window.setInterval(async () => {
    try {
      installTask.value = (await getPluginInstallTask(taskId)).data
      if (!installTaskRunning.value) {
        stopInstallTaskPolling()
        await loadWorkbench()
      }
    } catch (error) {
      stopInstallTaskPolling()
      noticeStore.show(getErrorMessage(error, t('plugins.manualInstallFailed')), 'error')
    }
  }, 1500)
}

function stopInstallTaskPolling() {
  if (installTaskPollTimer !== null) {
    window.clearInterval(installTaskPollTimer)
    installTaskPollTimer = null
  }
}

async function updatePluginItem(item: PluginWorkbenchItem) {
  if (!item.installed_package || packageTaskModule.value) {
    return
  }
  packageTaskModule.value = item.module_name
  try {
    const response = await updateInstalledPlugin(item.module_name, {
      package_name: item.installed_package,
    })
    packageTask.value = response.data
    packageTaskDialogVisible.value = true
    startPackageTaskPolling(response.data.task_id)
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('plugins.packageUpdateFailed')), 'error')
    packageTaskModule.value = ''
  }
}

function openUninstallConfirm(item: PluginWorkbenchItem) {
  uninstallConfirmItem.value = item
  uninstallRemoveConfig.value = false
  uninstallConfirmVisible.value = true
}

function closeUninstallConfirm() {
  uninstallConfirmVisible.value = false
  uninstallConfirmItem.value = null
  uninstallRemoveConfig.value = false
}

async function confirmUninstallAction() {
  if (!uninstallConfirmItem.value) {
    return
  }
  const item = uninstallConfirmItem.value
  uninstallingModule.value = item.module_name
  try {
    await uninstallPlugin(item.module_name, {
      remove_config: uninstallRemoveConfig.value,
    })
    restartStore.markPending({
      id: `plugin-uninstall:${item.module_name}`,
      scope: 'plugins',
      summary: t('restart.pendingPluginUninstall', {
        name: item.display_name,
      }),
    })
    noticeStore.show(t('plugins.settingsUninstallSucceeded'), 'success')
    closeUninstallConfirm()
    await loadWorkbench()
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('plugins.settingsUninstallFailed')), 'error')
  } finally {
    uninstallingModule.value = ''
  }
}

function startPackageTaskPolling(taskId: string) {
  stopPackageTaskPolling()
  packageTaskPollTimer = window.setInterval(async () => {
    try {
      packageTask.value = (await getPluginInstallTask(taskId)).data
      if (!packageTaskRunning.value) {
        stopPackageTaskPolling()
        if (packageTask.value?.status === 'succeeded') {
          restartStore.markPending({
            id: `plugin-package-update:${packageTaskModule.value || packageTask.value.binding_value || taskId}`,
            scope: 'plugins',
            summary: t('plugins.packageUpdateRestartPending', {
              name: packageTaskModule.value || packageTask.value.binding_value || '',
            }),
          })
          noticeStore.show(t('plugins.packageUpdateSucceeded'), 'success')
        }
        packageTaskModule.value = ''
        await loadWorkbench()
      }
    } catch (error) {
      stopPackageTaskPolling()
      packageTaskModule.value = ''
      noticeStore.show(getErrorMessage(error, t('plugins.packageUpdateFailed')), 'error')
    }
  }, 1500)
}

function stopPackageTaskPolling() {
  if (packageTaskPollTimer !== null) {
    window.clearInterval(packageTaskPollTimer)
    packageTaskPollTimer = null
  }
}

async function requestTogglePlugin(item: PluginWorkbenchItem, enabled: boolean) {
  if (!item.policy.can_change || item.is_pending_uninstall) {
    return
  }
  pendingModule.value = item.module_name
  toggleConfirmItem.value = item
  toggleConfirmNextValue.value = enabled
  toggleConfirmPreview.value = null
  toggleConfirmVisible.value = true
  try {
    toggleConfirmPreview.value = (await getPluginTogglePreview(
      item.module_name,
      enabled,
    )).data
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('plugins.updateFailed')), 'error')
    closeToggleConfirm()
  } finally {
    pendingModule.value = ''
  }
}

function closeToggleConfirm() {
  toggleConfirmVisible.value = false
  toggleConfirmItem.value = null
  toggleConfirmPreview.value = null
  toggleConfirmLoading.value = false
}

async function confirmToggleAction() {
  if (!toggleConfirmItem.value || !toggleConfirmAllowed.value) {
    return
  }
  toggleConfirmLoading.value = true
  pendingModule.value = toggleConfirmItem.value.module_name
  try {
    const response = await updatePlugin(
      toggleConfirmItem.value.module_name,
      toggleConfirmNextValue.value,
      true,
    )
    restartStore.markPending({
      id: `plugin-toggle:${response.data.module_name}`,
      scope: 'plugins',
      summary: t('restart.pendingPluginToggle', {
        name: toggleConfirmItem.value.display_name,
      }),
      undo: {
        kind: 'plugin-toggle',
        moduleName: response.data.module_name,
        enabled: !toggleConfirmNextValue.value,
      },
    })
    noticeStore.show(
      t('plugins.toggled', {
        name: toggleConfirmItem.value.display_name,
        action: toggleConfirmNextValue.value
          ? t('plugins.enabledAction')
          : t('plugins.disabledAction'),
      }),
      'success',
    )
    closeToggleConfirm()
    await loadWorkbench()
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('plugins.updateFailed')), 'error')
  } finally {
    pendingModule.value = ''
    toggleConfirmLoading.value = false
  }
}

async function runUpdateCheck() {
  if (checkingUpdates.value) {
    return
  }
  checkingUpdates.value = true
  try {
    await checkPluginUpdates({ force_refresh: true })
    noticeStore.show(t('plugins.updateLatest'), 'success')
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('plugins.updateCheckFailed')), 'error')
  } finally {
    checkingUpdates.value = false
  }
}

function openPluginSettings(item: PluginWorkbenchItem) {
  void pluginSettings.openSettings(item)
}

function openPluginReadme(item: PluginWorkbenchItem) {
  void pluginReadme.openReadme(item)
}

function openPluginDetail(item: PluginWorkbenchItem) {
  detailItem.value = item
  detailDialogVisible.value = true
}

function reloadOpenPluginRawSettings() {
  if (!pluginSettings.settingsPlugin.value) {
    return
  }
  void pluginSettings.loadPluginRawSettings(
    pluginSettings.settingsPlugin.value.module_name,
  )
}

function openPluginSettingsPreview() {
  void pluginSettings.openPluginSettingsPreview()
}

function openPluginRawPreview() {
  void pluginSettings.openPluginRawPreview()
}

function confirmPluginSettingsPreview() {
  void pluginSettings.confirmPreviewSave()
}

function projectUrl(item: PluginWorkbenchItem) {
  return pluginProjectUrl(item)
}

function sourceLabel(item: PluginWorkbenchItem) {
  return pluginSourceLabel(item.source, (key, params) => t(key, params || {}))
}

function sourceTone(item: PluginWorkbenchItem): WorkbenchTone {
  return pluginSourceTone(item.source)
}

function handleToggleChecked(item: PluginWorkbenchItem, value: boolean) {
  void requestTogglePlugin(item, value)
}

onMounted(() => {
  void loadWorkbench()
})

onBeforeUnmount(() => {
  stopInstallTaskPolling()
  stopPackageTaskPolling()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('plugins.workbenchDescription')"
    :title="t('plugins.workbenchTitle')"
  >
    <template #actions>
      <Button variant="secondary" :disabled="loading" @click="loadWorkbench">
        <RefreshCw :class="{ 'animate-spin': loading }" data-icon="inline-start" />
        {{ t('common.refresh') }}
      </Button>
      <Button variant="secondary" :disabled="checkingUpdates" @click="runUpdateCheck">
        <RefreshCw :class="{ 'animate-spin': checkingUpdates }" data-icon="inline-start" />
        {{ t('plugins.checkUpdates') }}
      </Button>
      <Button @click="openInstallDialog">
        <PackagePlus data-icon="inline-start" />
        {{ t('plugins.installPlugin') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" />

    <Alert v-if="maintenance?.orphan_config_count">
      <AlertCircle data-icon="inline-start" />
      <AlertDescription>
        {{ t('plugins.orphanConfigCount', { count: maintenance.orphan_config_count }) }}
      </AlertDescription>
    </Alert>

    <Panel :title="t('plugins.title')" :subtitle="t('plugins.workbenchListDescription')">
      <template #actions>
        <div class="plugins-workbench-toolbar">
          <div class="plugins-workbench-search">
            <Search data-icon="inline-start" />
            <Input v-model="searchQuery" :placeholder="t('plugins.search')" />
          </div>
          <ToggleGroup
            :model-value="filter"
            type="single"
            @update:model-value="value => value && (filter = String(value) as PluginFilter)"
          >
            <ToggleGroupItem
              v-for="option in filterOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </template>

      <LoadingSkeleton v-if="loading && plugins.length === 0" rows="8" />
      <EmptyState
        v-else-if="visiblePlugins.length === 0"
        :title="t('plugins.noVisiblePlugins')"
      />

      <div v-else class="plugins-workbench-grid">
        <article
          v-for="item in visiblePlugins"
          :key="item.module_name"
          class="plugin-card"
        >
          <div class="plugin-card__top">
            <div class="plugin-card__headline">
              <div class="plugin-card__title-row">
                <h2 class="plugin-card__title">
                  {{ item.display_name }}
                </h2>
                <StatusBadge :label="stateLabel(item)" :tone="stateTone(item)" />
              </div>
              <div class="plugin-card__subline">
                {{ item.module_name }}
              </div>
            </div>
            <Switch
              :disabled="!item.policy.can_change || pendingModule === item.module_name"
              :model-value="item.policy.enabled"
              @update:model-value="handleToggleChecked(item, Boolean($event))"
            />
          </div>

          <p class="plugin-card__description">
            {{ item.description || t('pluginStore.noDescription') }}
          </p>

          <div class="plugin-card__relations">
            <StatusBadge :label="sourceLabel(item)" :tone="sourceTone(item)" />
            <Badge v-if="item.installed_package" variant="outline">
              {{ item.installed_package }}
            </Badge>
            <Badge v-if="item.startup.requires_restart_to_apply_fully" variant="secondary">
              {{ t('dashboard.restart') }}
            </Badge>
          </div>

          <div v-if="restartHint(item)" class="plugin-card__dependency-list">
            {{ restartHint(item) }}
          </div>

          <div class="plugin-card__footer">
            <Button
              size="sm"
              variant="secondary"
              @click="openPluginDetail(item)"
            >
              <Info data-icon="inline-start" />
              {{ t('plugins.detail') }}
            </Button>
            <Button
              :disabled="!item.capabilities.can_edit_settings"
              size="sm"
              variant="ghost"
              @click="openPluginSettings(item)"
            >
              <FileCog data-icon="inline-start" />
              {{ t('plugins.settings') }}
            </Button>
            <Button
              :disabled="!item.capabilities.can_view_readme"
              size="sm"
              variant="ghost"
              @click="openPluginReadme(item)"
            >
              <FileText data-icon="inline-start" />
              {{ t('plugins.readme') }}
            </Button>
            <Button
              v-if="projectUrl(item)"
              as-child
              size="sm"
              variant="ghost"
            >
              <a :href="projectUrl(item)" rel="noreferrer" target="_blank">
                <Eye data-icon="inline-start" />
                {{ t('plugins.projectPage') }}
              </a>
            </Button>
            <Button
              :disabled="!item.capabilities.can_update_package || !item.installed_package || packageTaskModule === item.module_name"
              size="sm"
              variant="ghost"
              @click="updatePluginItem(item)"
            >
              <UploadCloud data-icon="inline-start" />
              {{ t('plugins.packageUpdate') }}
            </Button>
            <Button
              :disabled="!item.capabilities.can_uninstall || uninstallingModule === item.module_name"
              size="sm"
              variant="ghost"
              @click="openUninstallConfirm(item)"
            >
              <Trash2 data-icon="inline-start" />
              {{ t('plugins.settingsUninstall') }}
            </Button>
          </div>
        </article>
      </div>
    </Panel>

    <AlertDialog v-model:open="toggleConfirmVisible">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{{ toggleConfirmTitle }}</AlertDialogTitle>
          <AlertDialogDescription>
            {{ toggleConfirmSummary }}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div v-if="toggleConfirmItem" class="plugin-toggle-summary">
          <div>
            <strong>{{ toggleConfirmItem.display_name }}</strong>
            <span>{{ toggleConfirmItem.module_name }}</span>
          </div>
          <div v-if="toggleConfirmDependencies.length > 0" class="plugin-toggle-summary__relations">
            <Badge
              v-for="moduleName in toggleConfirmDependencies"
              :key="moduleName"
              variant="outline"
            >
              {{ pluginLabel(moduleName) }}
            </Badge>
          </div>
        </div>

        <Alert v-if="!toggleConfirmNextValue">
          <AlertCircle data-icon="inline-start" />
          <AlertDescription>{{ t('plugins.disableRuntimeSummary') }}</AlertDescription>
        </Alert>

        <AlertDialogFooter>
          <AlertDialogCancel @click="closeToggleConfirm">
            {{ t('common.cancel') }}
          </AlertDialogCancel>
          <AlertDialogAction
            :class="toggleConfirmNextValue ? '' : 'bg-destructive text-destructive-foreground hover:bg-destructive/90'"
            :disabled="toggleConfirmLoading || !toggleConfirmAllowed"
            @click="confirmToggleAction"
          >
            {{ toggleConfirmNextValue ? t('plugins.confirmEnable') : t('plugins.confirmDisable') }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <Dialog v-model:open="installDialogVisible">
      <DialogContent class="plugin-install-dialog">
        <DialogHeader>
          <DialogTitle>{{ t('plugins.installPlugin') }}</DialogTitle>
          <DialogDescription>{{ t('plugins.installPluginHint') }}</DialogDescription>
        </DialogHeader>

        <FieldGroup>
          <Field>
            <FieldLabel>{{ t('plugins.manualInstallSourceType') }}</FieldLabel>
            <Select v-model="installMode">
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="requirement">
                    {{ t('plugins.manualInstallPackageLabel') }}
                  </SelectItem>
                  <SelectItem value="store_item" @select="loadInstallStoreSources">
                    {{ t('plugins.installStoreItemLabel') }}
                  </SelectItem>
                  <SelectItem value="local_path">
                    {{ t('plugins.manualInstallLocalLabel') }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>

          <Field v-if="installMode === 'store_item'">
            <FieldLabel>{{ t('plugins.installStoreSource') }}</FieldLabel>
            <Select
              v-model="installStoreSourceId"
              @update:model-value="() => loadInstallStoreItems()"
            >
              <SelectTrigger>
                <SelectValue :placeholder="t('plugins.installStoreSource')" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem
                    v-for="source in installStoreSources"
                    :key="source.source_id"
                    :value="source.source_id"
                  >
                    {{ source.name }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>

          <Field v-if="installMode === 'store_item'">
            <FieldLabel>{{ t('plugins.installStoreSearch') }}</FieldLabel>
            <div class="plugin-install-store-search">
              <Input
                v-model.trim="installStoreSearch"
                :placeholder="t('plugins.installStoreSearch')"
                @keyup.enter="loadInstallStoreItems"
              />
              <Button
                :disabled="installStoreLoading"
                type="button"
                variant="secondary"
                @click="loadInstallStoreItems"
              >
                <Search data-icon="inline-start" />
                {{ t('common.search') }}
              </Button>
            </div>
          </Field>

          <Field v-if="installMode === 'store_item'">
            <FieldLabel>{{ t('plugins.installStoreItem') }}</FieldLabel>
            <Select v-model="installStoreItemId">
              <SelectTrigger>
                <SelectValue :placeholder="t('plugins.installStoreItem')" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem
                    v-for="item in installStoreItems"
                    :key="item.plugin_id"
                    :value="item.plugin_id"
                  >
                    {{ item.name }} - {{ item.module_name }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <FieldDescription>
              {{
                selectedStoreItem
                  ? `${selectedStoreItem.package_name} / ${selectedStoreItem.module_name}`
                  : t('plugins.installStoreEmpty')
              }}
            </FieldDescription>
          </Field>

          <Field v-if="installMode !== 'store_item'">
            <FieldLabel>
              {{
                installMode === 'local_path'
                  ? t('plugins.manualInstallLocalLabel')
                  : t('plugins.manualInstallPackageLabel')
              }}
            </FieldLabel>
            <Input
              v-model.trim="installSourceValue"
              :placeholder="installMode === 'local_path'
                ? t('plugins.manualInstallLocalHint')
                : t('plugins.manualInstallPackageHint')"
            />
            <FieldDescription>
              {{
                installMode === 'local_path'
                  ? t('plugins.installLocalHint')
                  : t('plugins.installRequirementHint')
              }}
            </FieldDescription>
          </Field>

          <Button
            :disabled="installResolving || !canResolveInstall"
            type="button"
            variant="secondary"
            @click="resolveInstall"
          >
            <Search data-icon="inline-start" />
            {{ t('plugins.resolveInstallSource') }}
          </Button>
        </FieldGroup>

        <Alert v-if="installResolution?.status === 'invalid'" variant="destructive">
          <AlertCircle data-icon="inline-start" />
          <AlertDescription>
            {{ installResolution.warnings.join(' ') || t('plugins.installResolveFailed') }}
          </AlertDescription>
        </Alert>

        <div v-if="installResolution" class="plugin-install-resolution">
          <StatusBadge
            :label="t(`plugins.installStatus.${installResolution.status}`)"
            :tone="installResolution.status === 'invalid'
              ? 'error'
              : installResolution.status === 'resolved'
                ? 'success'
                : 'warning'"
          />

          <Field
            v-if="installNeedsCandidateChoice"
          >
            <FieldLabel>{{ t('plugins.installChooseModule') }}</FieldLabel>
            <Select v-model="installSelectedModule">
              <SelectTrigger>
                <SelectValue :placeholder="t('plugins.installChooseModule')" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem
                    v-for="candidate in installResolutionCandidates"
                    :key="candidate.module_name"
                    :value="candidate.module_name"
                  >
                    {{ candidate.module_name }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>

          <Field v-if="installNeedsManualModule">
            <FieldLabel>{{ t('plugins.manualInstallModule') }}</FieldLabel>
            <Input v-model.trim="installManualModule" />
            <FieldDescription>{{ t('plugins.manualInstallModuleHint') }}</FieldDescription>
          </Field>

          <div
            v-if="installResolutionCandidates.length > 0"
            class="plugin-install-resolution__candidates"
          >
            <Badge
              v-for="candidate in installResolutionCandidates"
              :key="candidate.module_name"
              variant="outline"
            >
              {{ candidate.module_name }}
            </Badge>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" @click="installDialogVisible = false">
            {{ t('common.cancel') }}
          </Button>
          <Button :disabled="!canConfirmInstall" @click="confirmInstallAction">
            <PackagePlus data-icon="inline-start" />
            {{ t('plugins.manualInstallSubmit') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <TaskDialog
      v-model="installTaskDialogVisible"
      :binding-value="installTask?.binding_value"
      :close-label="t('common.close')"
      :current-phase="installTask?.current_phase"
      :current-phase-label="installTask?.current_phase_label"
      :diagnostics="installTask?.diagnostics || []"
      :loading="installTaskRunning"
      :logs="installTask?.logs || ''"
      :operation="installTask?.operation"
      :queue-position="installTask?.queue_position"
      :requirement="installTask?.requirement"
      :resource-kind="installTask?.resource_kind"
      :restart-required="installTask?.restart_required"
      :status="installTask?.status || ''"
      :status-tone="installTask?.status === 'failed' ? 'error' : installTask?.status === 'succeeded' ? 'success' : 'info'"
      :steps="installTask?.steps || []"
      :title="installTask?.title || t('plugins.manualInstallTaskTitle')"
      :waiting-text="t('plugins.manualInstallWaiting')"
    />

    <TaskDialog
      v-model="packageTaskDialogVisible"
      :binding-value="packageTask?.binding_value"
      :close-label="t('common.close')"
      :current-phase="packageTask?.current_phase"
      :current-phase-label="packageTask?.current_phase_label"
      :diagnostics="packageTask?.diagnostics || []"
      :loading="packageTaskRunning"
      :logs="packageTask?.logs || ''"
      :operation="packageTask?.operation"
      :queue-position="packageTask?.queue_position"
      :requirement="packageTask?.requirement"
      :resource-kind="packageTask?.resource_kind"
      :restart-required="packageTask?.restart_required"
      :status="packageTask?.status || ''"
      :status-tone="packageTask?.status === 'failed' ? 'error' : packageTask?.status === 'succeeded' ? 'success' : 'info'"
      :steps="packageTask?.steps || []"
      :title="packageTask?.title || t('plugins.packageUpdateTaskTitle')"
      :waiting-text="t('plugins.packageUpdateWaiting')"
    />

    <AlertDialog v-model:open="uninstallConfirmVisible">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{{ t('plugins.settingsUninstall') }}</AlertDialogTitle>
          <AlertDialogDescription v-if="uninstallConfirmItem">
            {{
              uninstallConfirmItem.installed_package
                ? t('plugins.settingsUninstallConfirm', {
                    name: uninstallConfirmItem.display_name,
                    package: uninstallConfirmItem.installed_package,
                  })
                : t('plugins.settingsUninstallConfirmFallback', {
                    name: uninstallConfirmItem.display_name,
                  })
            }}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <label class="plugin-uninstall-option">
          <Checkbox v-model:checked="uninstallRemoveConfig" />
          <span>
            <strong>{{ t('plugins.settingsUninstallRemoveConfig') }}</strong>
            <small>{{ t('plugins.settingsUninstallRemoveConfigHint') }}</small>
          </span>
        </label>

        <AlertDialogFooter>
          <AlertDialogCancel @click="closeUninstallConfirm">
            {{ t('common.cancel') }}
          </AlertDialogCancel>
          <AlertDialogAction
            class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            :disabled="Boolean(uninstallingModule)"
            @click="confirmUninstallAction"
          >
            {{ t('plugins.settingsUninstall') }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <Dialog v-model:open="detailDialogVisible">
      <DialogContent class="plugin-detail-dialog">
        <DialogHeader>
          <DialogTitle>
            {{ detailItem?.display_name || detailItem?.module_name }}
          </DialogTitle>
          <DialogDescription>{{ detailItem?.module_name }}</DialogDescription>
        </DialogHeader>

        <div v-if="detailItem" class="plugin-detail-grid">
          <section>
            <h3>{{ t('plugins.detailRuntime') }}</h3>
            <p>{{ restartHint(detailItem) || stateLabel(detailItem) }}</p>
            <div class="plugin-detail-badges">
              <StatusBadge :label="stateLabel(detailItem)" :tone="stateTone(detailItem)" />
              <Badge variant="outline">
                {{ detailItem.runtime.loaded ? t('plugins.loaded') : t('plugins.notLoaded') }}
              </Badge>
              <Badge v-if="detailItem.runtime.execution_blocked" variant="secondary">
                {{ t('plugins.stateExecutionBlocked') }}
              </Badge>
              <Badge v-if="detailItem.startup.requires_restart_to_apply_fully" variant="secondary">
                {{ t('dashboard.restart') }}
              </Badge>
            </div>
          </section>

          <section>
            <h3>{{ t('plugins.detailPolicyImpact') }}</h3>
            <p>
              {{
                detailItem.policy.enabled
                  ? t('plugins.enableRuntimeSummary')
                  : t('plugins.disableRuntimeSummary')
              }}
            </p>
            <div class="plugin-detail-badges">
              <Badge variant="outline">
                {{ detailItem.startup.will_load ? t('plugins.loaded') : t('plugins.stateNotLoaded') }}
              </Badge>
              <Badge v-if="!detailItem.policy.can_change" variant="secondary">
                {{ detailItem.policy.locked_reason || t('plugins.protected') }}
              </Badge>
            </div>
          </section>

          <section>
            <h3>{{ t('plugins.detailPackage') }}</h3>
            <p>{{ detailItem.installed_package || t('common.none') }}</p>
            <div class="plugin-detail-badges">
              <Badge v-for="moduleName in detailItem.installed_module_names" :key="moduleName" variant="outline">
                {{ moduleName }}
              </Badge>
            </div>
          </section>

          <section>
            <h3>{{ t('plugins.detailDependencies') }}</h3>
            <div class="plugin-detail-badges">
              <Badge v-for="moduleName in detailItem.required_plugins" :key="`req-${moduleName}`" variant="outline">
                {{ t('plugins.requires', { name: pluginLabel(moduleName) }) }}
              </Badge>
              <Badge v-for="moduleName in detailItem.dependent_plugins" :key="`dep-${moduleName}`" variant="outline">
                {{ t('plugins.requiredBy', { name: pluginLabel(moduleName) }) }}
              </Badge>
              <Badge v-for="moduleName in detailItem.child_plugins" :key="`child-${moduleName}`" variant="outline">
                {{ moduleName }}
              </Badge>
            </div>
          </section>
        </div>

        <DialogFooter>
          <Button
            :disabled="!detailItem?.capabilities.can_edit_settings"
            variant="secondary"
            @click="detailItem && openPluginSettings(detailItem)"
          >
            <FileCog data-icon="inline-start" />
            {{ t('plugins.settings') }}
          </Button>
          <Button
            :disabled="!detailItem?.capabilities.can_view_readme"
            variant="ghost"
            @click="detailItem && openPluginReadme(detailItem)"
          >
            <FileText data-icon="inline-start" />
            {{ t('plugins.readme') }}
          </Button>
          <Button variant="ghost" @click="detailDialogVisible = false">
            {{ t('common.close') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="pluginReadme.readmeDialogVisible.value">
      <DialogContent class="plugin-readme-dialog">
        <DialogHeader>
          <DialogTitle>{{ pluginReadme.readmeDialogTitle.value }}</DialogTitle>
          <DialogDescription v-if="pluginReadme.readmeFilename.value">
            {{ pluginReadme.readmeFilename.value }}
          </DialogDescription>
        </DialogHeader>

        <Alert v-if="pluginReadme.readmeErrorMessage.value" variant="destructive">
          <AlertCircle data-icon="inline-start" />
          <AlertDescription>{{ pluginReadme.readmeErrorMessage.value }}</AlertDescription>
        </Alert>
        <LoadingSkeleton v-else-if="pluginReadme.readmeLoading.value" rows="8" />
        <div
          v-else
          class="plugin-readme-content markdown-content"
          v-html="pluginReadme.readmeHtml.value"
        />

        <DialogFooter>
          <Button variant="ghost" @click="pluginReadme.readmeDialogVisible.value = false">
            {{ t('common.close') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="pluginSettings.settingsDialogVisible.value">
      <DialogContent class="plugin-settings-dialog">
        <DialogHeader>
          <DialogTitle>
            {{
              t('plugins.settingsTitle', {
                name: pluginSettings.settingsPlugin.value?.name
                  || pluginSettings.settingsPlugin.value?.module_name
                  || '',
              })
            }}
          </DialogTitle>
          <DialogDescription>
            {{ pluginSettings.settingsPlugin.value?.module_name }}
          </DialogDescription>
        </DialogHeader>

        <Alert v-if="pluginSettings.settingsErrorMessage.value" variant="destructive">
          <AlertCircle data-icon="inline-start" />
          <AlertDescription>{{ pluginSettings.settingsErrorMessage.value }}</AlertDescription>
        </Alert>

        <LoadingSkeleton v-if="pluginSettings.settingsDialogLoading.value" rows="7" />

        <Tabs
          v-else
          v-model="pluginSettings.settingsEditorMode.value"
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
              v-if="pluginSettings.settingsEditorMode.value === 'basic'"
              :disabled="!pluginSettings.hasPendingPluginChanges.value || pluginSettings.settingsSaving.value"
              size="sm"
              @click="openPluginSettingsPreview"
            >
              <Save data-icon="inline-start" />
              {{ t('plugins.settingsSave') }}
            </Button>
          </div>

          <TabsContent value="basic" class="plugin-settings-tab-content">
            <EmptyState
              v-if="!pluginSettings.settingsState.value?.has_config_model
                || pluginSettings.settingsFields.value.length === 0"
              :title="t('plugins.settingsEmpty')"
            />

            <div v-else class="settings-list-panel plugin-settings-list">
              <article
                v-for="field in pluginSettings.settingsFields.value"
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
                        v-if="field.has_local_override || pluginSettings.pluginEditor.isFieldEditing(field)"
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
                      {{ pluginSettings.displayFieldValue(field.current_value) }}
                    </div>
                  </div>

                  <div class="settings-list-row__control">
                    <div class="settings-list-row__actions">
                      <Button
                        v-if="!pluginSettings.pluginEditor.isFieldEditing(field) && field.editable"
                        size="sm"
                        variant="secondary"
                        @click="pluginSettings.pluginEditor.startOverride(field)"
                      >
                        {{ t('plugins.settingsAddOverride') }}
                      </Button>
                      <Button
                        v-if="pluginSettings.pluginEditor.isFieldEditing(field)"
                        size="sm"
                        variant="ghost"
                        @click="pluginSettings.pluginEditor.cancelField(field)"
                      >
                        {{ t('common.cancel') }}
                      </Button>
                      <Button
                        v-if="field.has_local_override"
                        size="sm"
                        variant="ghost"
                        @click="pluginSettings.clearPluginField(field)"
                      >
                        {{ t('plugins.settingsClear') }}
                      </Button>
                    </div>

                    <div class="settings-field-editor">
                      <Select
                        v-if="pluginSettings.fieldChoiceOptions(field).length > 0"
                        :model-value="pluginSettings.selectedFieldChoiceKey(field)"
                        :disabled="!pluginSettings.pluginEditor.isFieldEditing(field)"
                        @update:model-value="value => pluginSettings.updateFieldChoice(field, value as string | number)"
                      >
                        <SelectTrigger class="settings-field-editor__control">
                          <SelectValue :placeholder="t('common.none')" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            <SelectItem
                              v-for="choice in pluginSettings.fieldChoiceOptions(field)"
                              :key="choice.key"
                              :value="choice.key"
                            >
                              {{ choice.title }}
                            </SelectItem>
                          </SelectGroup>
                        </SelectContent>
                      </Select>

                      <label
                        v-else-if="field.type === 'bool' && !pluginSettings.isNullableBoolField(field)"
                        class="settings-field-editor__switch"
                      >
                        <Switch
                          :disabled="!pluginSettings.pluginEditor.isFieldEditing(field)"
                          :model-value="Boolean(pluginSettings.settingsForm.value[field.key])"
                          @update:model-value="value => {
                            pluginSettings.settingsForm.value[field.key] = Boolean(value)
                          }"
                        />
                        <span>
                          {{
                            pluginSettings.settingsForm.value[field.key]
                              ? t('ai.enabled')
                              : t('ai.disabled')
                          }}
                        </span>
                      </label>

                      <Textarea
                        v-else-if="field.type_category === 'mapping'
                          || (field.type_category === 'sequence' && !pluginSettings.isSequenceChipField(field))
                          || field.editor.startsWith('nested_')"
                        v-model="pluginSettings.settingsForm.value[field.key] as string"
                        class="settings-field-editor__code"
                        :disabled="!pluginSettings.pluginEditor.isFieldEditing(field)"
                        spellcheck="false"
                      />

                      <Input
                        v-else
                        v-model="pluginSettings.settingsForm.value[field.key] as string | number"
                        class="settings-field-editor__control"
                        :disabled="!pluginSettings.pluginEditor.isFieldEditing(field)"
                        :type="pluginSettings.textInputType(field)"
                      />
                    </div>
                  </div>
                </div>
              </article>
            </div>
          </TabsContent>

          <TabsContent value="advanced" class="plugin-settings-tab-content">
            <RawSettingsEditor
              v-model="pluginSettings.settingsRawText.value"
              :description="t('plugins.settingsAdvancedDescription')"
              :dirty="pluginSettings.hasPendingPluginRawChanges.value"
              :error-message="pluginSettings.settingsRawErrorMessage.value"
              :loading="pluginSettings.settingsRawLoading.value"
              :reload-label="t('common.refresh')"
              :save-label="t('plugins.settingsSave')"
              :saving="pluginSettings.settingsRawSaving.value"
              :validation-error-column="pluginSettings.pluginRawValidationColumn.value"
              :validation-error-line="pluginSettings.pluginRawValidationLine.value"
              :validation-error-message="pluginSettings.pluginRawValidationMessage.value"
              :validation-pending="pluginSettings.pluginRawValidationPending.value"
              @reload="reloadOpenPluginRawSettings"
              @save="openPluginRawPreview"
            />
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button variant="ghost" @click="pluginSettings.closeSettingsDialog">
            {{ t('common.close') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="pluginSettings.previewDialogVisible.value">
      <DialogContent class="settings-preview-dialog">
        <DialogHeader>
          <DialogTitle>{{ pluginSettings.previewTitle.value }}</DialogTitle>
          <DialogDescription>{{ t('plugins.settingsRestartHint') }}</DialogDescription>
        </DialogHeader>

        <Table v-if="pluginSettings.previewMode.value === 'basic'">
          <TableHeader>
            <TableRow>
              <TableHead>{{ t('plugins.settingsField') }}</TableHead>
              <TableHead>{{ t('plugins.previewCurrent') }}</TableHead>
              <TableHead>{{ t('plugins.previewNext') }}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="item in pluginSettings.previewItems.value"
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
            <pre>{{ pluginSettings.previewCurrentText.value }}</pre>
          </div>
          <div class="settings-raw-preview-block">
            <div class="settings-raw-preview-block__label">
              {{ t('plugins.previewNext') }}
            </div>
            <pre>{{ pluginSettings.previewNextText.value }}</pre>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" @click="pluginSettings.previewDialogVisible.value = false">
            {{ t('common.cancel') }}
          </Button>
          <Button
            :disabled="pluginSettings.previewSaving.value"
            @click="confirmPluginSettingsPreview"
          >
            <Save data-icon="inline-start" />
            {{ t('plugins.confirmSave') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </PageScaffold>
</template>
