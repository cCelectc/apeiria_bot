<script setup lang="ts">
import type { PluginItem, PluginTogglePreview } from '@/api/plugins'
import type { WorkbenchMetricItem, WorkbenchTone } from '@/components/management'
import {
  AlertCircle,
  Boxes,
  Code2,
  FileText,
  ExternalLink,
  FileCog,
  PackageOpen,
  Puzzle,
  RefreshCw,
  Save,
  Settings,
  ShieldCheck,
  Trash2,
  UploadCloud,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { getErrorMessage } from '@/api/client'
import {
  getPluginTogglePreview,
  getPlugins,
  normalizePluginsResponse,
  updatePlugin,
} from '@/api/plugins'
import {
  EmptyState,
  FilterBar,
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
import { usePluginMaintenance } from '@/composables/usePluginMaintenance'
import { usePluginReadmeDialog } from '@/composables/usePluginReadmeDialog'
import { usePluginSettingsDialog } from '@/composables/usePluginSettingsDialog'
import { useAuthStore } from '@/stores/auth'
import { useNoticeStore } from '@/stores/notice'
import { useRestartStore } from '@/stores/restart'
import {
  pluginMetaSummary,
  pluginProjectUrl,
  pluginSourceLabel,
  pluginSourceTone,
  pluginToggleHint,
  settingsSourceLabel,
} from '@/utils/pluginDisplay'

type PluginScopeTab = 'managed' | 'framework'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const noticeStore = useNoticeStore()
const restartStore = useRestartStore()
const plugins = ref<PluginItem[]>([])
const loading = ref(false)
const errorMessage = ref('')
const pluginSearch = ref('')
const pluginScopeTab = ref<PluginScopeTab>('managed')
const pendingModule = ref('')
const toggleConfirmVisible = ref(false)
const toggleConfirmLoading = ref(false)
const toggleConfirmItem = ref<PluginItem | null>(null)
const toggleConfirmPreview = ref<PluginTogglePreview | null>(null)
const toggleConfirmNextValue = ref(false)
const pluginSettings = usePluginSettingsDialog({
  noticeStore,
  restartStore,
  t: (key, params) => t(key, params || {}),
})
const pluginReadme = usePluginReadmeDialog((key, params) => t(key, params || {}))
const pluginMaintenance = usePluginMaintenance({
  loadPluginManagement,
  noticeStore,
  restartStore,
  t: (key, params) => t(key, params || {}),
})

const systemPlugins = computed(() =>
  plugins.value.filter(item => item.source === 'framework' || item.is_dependency),
)
const nonSystemPlugins = computed(() =>
  plugins.value.filter(item => item.source !== 'framework' && !item.is_dependency),
)
const scopedPlugins = computed(() =>
  pluginScopeTab.value === 'framework' ? systemPlugins.value : nonSystemPlugins.value,
)
const visiblePlugins = computed(() => {
  const query = pluginSearch.value.trim().toLowerCase()
  if (!query) {
    return scopedPlugins.value
  }
  return scopedPlugins.value.filter(item =>
    [
      item.name,
      item.module_name,
      item.description,
      item.author,
      item.version,
    ].some(value => String(value || '').toLowerCase().includes(query)),
  )
})
const enabledCount = computed(() =>
  plugins.value.filter(item => item.is_global_enabled).length,
)
const protectedCount = computed(() =>
  plugins.value.filter(item => item.is_protected).length,
)
const pluginMetrics = computed<WorkbenchMetricItem[]>(() => [
  {
    key: 'managed',
    label: t('plugins.userManagedCount'),
    value: nonSystemPlugins.value.length,
    icon: Puzzle,
    tone: 'info',
  },
  {
    key: 'framework',
    label: t('plugins.coreProtectedCount'),
    value: systemPlugins.value.length,
    icon: ShieldCheck,
    tone: 'warning',
  },
  {
    key: 'enabled',
    label: t('plugins.enabled'),
    value: `${enabledCount.value}/${plugins.value.length}`,
    icon: Boxes,
    tone: 'success',
  },
  {
    key: 'protected',
    label: t('plugins.protected'),
    value: protectedCount.value,
    icon: ShieldCheck,
  },
])
const toggleConfirmTitle = computed(() =>
  toggleConfirmNextValue.value
    ? t('plugins.enableConfirmTitle')
    : t('plugins.disableConfirmTitle'),
)
const toggleConfirmSummary = computed(() => {
  if (toggleConfirmPreview.value?.blocked_reason) {
    return toggleConfirmPreview.value.blocked_reason
  }
  return toggleConfirmPreview.value?.summary
    || (
      toggleConfirmNextValue.value
        ? t('plugins.confirmEnable')
        : t('plugins.disableConfirmSummary')
    )
})
const toggleConfirmDependencies = computed(() => {
  const preview = toggleConfirmPreview.value
  if (!preview) {
    return []
  }
  return toggleConfirmNextValue.value
    ? [...preview.requires_enable, ...preview.missing_dependencies]
    : [...preview.requires_disable, ...preview.protected_dependents]
})
const toggleConfirmAllowed = computed(() =>
  Boolean(toggleConfirmPreview.value?.allowed),
)

async function loadPluginManagement(options?: { forceUpdateRefresh?: boolean }) {
  loading.value = true
  errorMessage.value = ''
  try {
    plugins.value = normalizePluginsResponse((await getPlugins()).data)
    await pluginMaintenance.runPluginUpdateCheck(options?.forceUpdateRefresh === true)
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('plugins.loadFailed'))
  } finally {
    loading.value = false
  }
}

function pluginStatusTone(item: PluginItem): WorkbenchTone {
  if (item.is_pending_uninstall) {
    return 'warning'
  }
  if (!item.is_loaded) {
    return 'default'
  }
  return item.is_global_enabled ? 'success' : 'warning'
}

function pluginStatusLabel(item: PluginItem) {
  if (item.is_pending_uninstall) {
    return t('plugins.pendingUninstall')
  }
  if (!item.is_loaded) {
    return t('plugins.notLoaded')
  }
  return item.is_global_enabled ? t('ai.enabled') : t('ai.disabled')
}

function pluginLabel(moduleName: string) {
  const match = plugins.value.find(item => item.module_name === moduleName)
  return match?.name || match?.module_name || moduleName
}

async function requestTogglePlugin(item: PluginItem, enabled: boolean) {
  if (!item.can_enable_disable || item.is_protected || item.is_pending_uninstall) {
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

function handleToggleChecked(item: PluginItem, value: boolean) {
  void requestTogglePlugin(item, value)
}

function setPluginScopeTab(value: unknown) {
  if (value === 'managed' || value === 'framework') {
    pluginScopeTab.value = value
  }
}

function closeToggleConfirm() {
  toggleConfirmVisible.value = false
  toggleConfirmItem.value = null
  toggleConfirmPreview.value = null
  toggleConfirmLoading.value = false
}

async function confirmToggleAction() {
  if (!toggleConfirmItem.value || !toggleConfirmPreview.value?.allowed) {
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
        name: toggleConfirmItem.value.name || toggleConfirmItem.value.module_name,
      }),
      undo: {
        kind: 'plugin-toggle',
        moduleName: response.data.module_name,
        enabled: !toggleConfirmNextValue.value,
      },
    })
    noticeStore.show(
      t('plugins.toggled', {
        name: toggleConfirmItem.value.name || toggleConfirmItem.value.module_name,
        action: toggleConfirmNextValue.value
          ? t('plugins.enabledAction')
          : t('plugins.disabledAction'),
      }),
      'success',
    )
    closeToggleConfirm()
    await loadPluginManagement()
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('plugins.updateFailed')), 'error')
  } finally {
    pendingModule.value = ''
    toggleConfirmLoading.value = false
  }
}

function openPluginStore() {
  void router.push({ name: 'plugins', query: { area: 'store' } })
}

function openPluginSettings(item: PluginItem) {
  void pluginSettings.openSettings(item)
}

function openPluginReadme(item: PluginItem) {
  void pluginReadme.openReadme(item)
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

function pluginSettingsSourceLabel(source: string) {
  return settingsSourceLabel(source, (key, params) => t(key, params || {}))
}

function runPluginUpdateCheck() {
  void pluginMaintenance.runPluginUpdateCheck(true)
}

function canUninstallPlugin(item: PluginItem) {
  return pluginMaintenance.canUninstallPlugin(authStore.role, item)
}

function canUpdatePlugin(item: PluginItem) {
  return pluginMaintenance.canUpdatePlugin(authStore.role, item)
}

function hasPluginUpdate(item: PluginItem) {
  return pluginMaintenance.hasPluginUpdate(item)
}

function updateButtonTooltip(item: PluginItem) {
  return pluginMaintenance.updateButtonTooltip(item)
}

function openManualInstallDialog() {
  pluginMaintenance.openManualInstallDialog()
}

function openOrphanConfigDialog() {
  void pluginMaintenance.openOrphanConfigDialog()
}

function openUninstallConfirm(item: PluginItem) {
  pluginMaintenance.openUninstallConfirm(item)
}

function confirmUninstallPlugin() {
  void pluginMaintenance.confirmUninstallPlugin()
}

function confirmCleanupOrphanConfigs() {
  void pluginMaintenance.confirmCleanupOrphanConfigs()
}

function submitManualInstall() {
  void pluginMaintenance.submitManualInstall()
}

function updatePluginItem(item: PluginItem) {
  void pluginMaintenance.updatePluginItem(item)
}

onMounted(() => {
  void loadPluginManagement()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :kicker="t('layout.pluginsGroup')"
    :subtitle="t('plugins.configDescription')"
    :title="t('plugins.title')"
  >
    <template #actions>
      <Button
        v-if="authStore.role === 'owner'"
        :disabled="pluginMaintenance.manualInstallSubmitting.value"
        @click="openManualInstallDialog"
      >
        <UploadCloud :size="16" />
        {{ t('plugins.manualInstall') }}
      </Button>
      <Button
        v-if="authStore.role === 'owner'"
        :disabled="pluginMaintenance.updateCheckLoading.value"
        variant="secondary"
        @click="runPluginUpdateCheck"
      >
        <RefreshCw
          :class="{ 'animate-spin': pluginMaintenance.updateCheckLoading.value }"
          :size="16"
        />
        {{
          pluginMaintenance.updateCheckLoading.value
            ? t('plugins.checkingUpdates')
            : t('plugins.checkUpdates')
        }}
      </Button>
      <Button
        v-if="authStore.role === 'owner'"
        :disabled="pluginMaintenance.orphanConfigLoading.value"
        variant="outline"
        @click="openOrphanConfigDialog"
      >
        <Trash2 :size="16" />
        {{ t('plugins.orphanConfigCleanup') }}
      </Button>
      <Button :disabled="loading" variant="secondary" @click="loadPluginManagement">
        <RefreshCw :class="{ 'animate-spin': loading }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
      <Button variant="outline" @click="openPluginStore">
        <PackageOpen :size="16" />
        {{ t('plugins.openStore') }}
      </Button>
    </template>

    <MetricStrip :items="pluginMetrics" />

    <Panel>
      <FilterBar compact>
        <div class="plugins-toolbar">
          <div class="plugins-search">
            <Input
              v-model.trim="pluginSearch"
              :aria-label="t('plugins.search')"
              :placeholder="t('plugins.search')"
            />
          </div>

          <ToggleGroup
            :model-value="pluginScopeTab"
            :aria-label="t('plugins.scopeTabs')"
            class="plugins-scope-tabs"
            size="sm"
            type="single"
            variant="outline"
            @update:model-value="setPluginScopeTab"
          >
            <ToggleGroupItem value="managed">
              {{ t('plugins.tabManaged') }}
            </ToggleGroupItem>
            <ToggleGroupItem value="framework">
              {{ t('plugins.tabFramework') }}
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </FilterBar>
    </Panel>

    <LoadingSkeleton v-if="loading && plugins.length === 0" rows="8" />
    <EmptyState
      v-else-if="visiblePlugins.length === 0"
      :icon="Puzzle"
      :title="t('plugins.noVisiblePlugins')"
    />

    <div v-else class="plugins-grid">
      <article
        v-for="item in visiblePlugins"
        :key="item.module_name"
        class="plugin-card"
      >
        <div class="plugin-card__top">
          <div class="plugin-card__headline">
            <div class="plugin-card__title-row">
              <h2 class="plugin-card__title">
                {{ item.name || item.module_name }}
              </h2>
              <StatusBadge :label="pluginStatusLabel(item)" :tone="pluginStatusTone(item)" />
              <StatusBadge
                :label="pluginSourceLabel(item.source, (key, params) => t(key, params || {}))"
                :tone="pluginSourceTone(item.source)"
              />
            </div>

            <div class="plugin-card__subline">
              {{ item.module_name }}
            </div>
            <div v-if="pluginMetaSummary(item)" class="plugin-card__subline">
              {{ pluginMetaSummary(item) }}
            </div>
          </div>
        </div>

        <p class="plugin-card__description">
          {{ item.description || t('common.noData') }}
        </p>

        <div class="plugin-card__relations">
          <Badge v-if="item.admin_level > 0" variant="secondary">
            Lv.{{ item.admin_level }}
          </Badge>
          <Badge variant="outline">
            {{ item.plugin_type }}
          </Badge>
          <Badge v-if="item.is_explicit" variant="secondary">
            {{ t('plugins.explicit') }}
          </Badge>
          <Badge v-if="item.is_dependency" variant="outline">
            {{ t('plugins.dependency') }}
          </Badge>
          <Badge v-if="item.is_protected" variant="outline">
            {{ t('plugins.protected') }}
          </Badge>
          <Badge v-if="item.child_plugins.length > 0" variant="outline">
            {{ t('plugins.childPluginCount', { count: item.child_plugins.length }) }}
          </Badge>
        </div>

        <div
          v-if="item.required_plugins.length > 0 || item.dependent_plugins.length > 0"
          class="plugin-card__dependency-list"
        >
          <span v-if="item.required_plugins.length > 0">
            {{ t('plugins.requiredCountHint', { count: item.required_plugins.length }) }}
          </span>
          <span v-if="item.dependent_plugins.length > 0">
            {{ t('plugins.dependentCountHint', { count: item.dependent_plugins.length }) }}
          </span>
        </div>

        <div class="plugin-card__footer">
          <Button
            v-if="canUninstallPlugin(item)"
            :disabled="pluginMaintenance.uninstallingModule.value === item.module_name"
            size="sm"
            variant="ghost"
            @click="openUninstallConfirm(item)"
          >
            <Trash2 :size="15" />
            {{ t('plugins.settingsUninstall') }}
          </Button>

          <Button
            v-if="pluginProjectUrl(item)"
            as="a"
            :href="pluginProjectUrl(item)"
            rel="noopener noreferrer"
            size="sm"
            target="_blank"
            variant="ghost"
          >
            <ExternalLink :size="15" />
            {{ t('plugins.projectPage') }}
          </Button>

          <Button
            v-if="item.can_view_readme"
            :disabled="pluginReadme.readmeLoadingModule.value === item.module_name"
            size="sm"
            variant="ghost"
            @click="openPluginReadme(item)"
          >
            <FileText :size="15" />
            {{ t('plugins.readme') }}
          </Button>

          <Button
            v-if="item.can_edit_config"
            :disabled="pluginSettings.settingsLoadingModule.value === item.module_name"
            size="sm"
            variant="ghost"
            @click="openPluginSettings(item)"
          >
            <Settings :size="15" />
            {{ t('plugins.settings') }}
          </Button>

          <Button
            v-if="canUpdatePlugin(item)"
            :disabled="pluginMaintenance.updateCheckLoading.value || !hasPluginUpdate(item) || pluginMaintenance.packageUpdatingModule.value === item.module_name"
            size="sm"
            :title="updateButtonTooltip(item)"
            :variant="hasPluginUpdate(item) ? 'secondary' : 'ghost'"
            @click="updatePluginItem(item)"
          >
            <RefreshCw
              :class="{
                'animate-spin': pluginMaintenance.packageUpdatingModule.value === item.module_name,
              }"
              :size="15"
            />
            {{ t('plugins.packageUpdate') }}
          </Button>

          <label
            v-if="item.can_enable_disable || item.is_protected || item.is_pending_uninstall"
            class="plugin-card__switch"
            :title="pluginToggleHint(item, (key, params) => t(key, params || {}))"
          >
            <Switch
              :checked="item.is_global_enabled"
              :disabled="!item.can_enable_disable || item.is_protected || item.is_pending_uninstall || pendingModule === item.module_name"
              @update:checked="(value: boolean) => handleToggleChecked(item, value)"
            />
          </label>
        </div>
      </article>
    </div>

    <AlertDialog v-model:open="toggleConfirmVisible">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{{ toggleConfirmTitle }}</AlertDialogTitle>
          <AlertDialogDescription>{{ toggleConfirmSummary }}</AlertDialogDescription>
        </AlertDialogHeader>

        <div v-if="toggleConfirmItem" class="plugin-toggle-summary">
          <div>
            <strong>{{ toggleConfirmItem.name || toggleConfirmItem.module_name }}</strong>
            <span>{{ toggleConfirmItem.module_name }}</span>
          </div>

          <div v-if="toggleConfirmDependencies.length > 0" class="plugin-toggle-summary__relations">
            <Badge
              v-for="moduleName in toggleConfirmDependencies"
              :key="moduleName"
              variant="outline"
            >
              {{
                toggleConfirmNextValue
                  ? t('plugins.requires', { name: pluginLabel(moduleName) })
                  : t('plugins.requiredBy', { name: pluginLabel(moduleName) })
              }}
            </Badge>
          </div>
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel @click="closeToggleConfirm">
            {{ t('common.cancel') }}
          </AlertDialogCancel>
          <AlertDialogAction
            :class="toggleConfirmNextValue ? '' : 'bg-destructive text-destructive-foreground hover:bg-destructive/90'"
            :disabled="!toggleConfirmAllowed"
            @click="confirmToggleAction"
          >
            {{ toggleConfirmNextValue ? t('plugins.confirmEnable') : t('plugins.confirmDisable') }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <Dialog v-model:open="pluginReadme.readmeDialogVisible.value">
      <DialogContent class="plugin-readme-dialog">
        <DialogHeader>
          <DialogTitle>{{ pluginReadme.readmeDialogTitle.value }}</DialogTitle>
          <DialogDescription v-if="pluginReadme.readmeFilename.value">
            {{ pluginReadme.readmeFilename.value }}
          </DialogDescription>
        </DialogHeader>

        <Alert v-if="pluginReadme.readmeErrorMessage.value" variant="destructive">
          <AlertCircle :size="16" />
          <AlertDescription>{{ pluginReadme.readmeErrorMessage.value }}</AlertDescription>
        </Alert>
        <LoadingSkeleton v-else-if="pluginReadme.readmeLoading.value" rows="8" />
        <div
          v-else
          class="plugin-readme-content markdown-content"
          v-html="pluginReadme.readmeHtml.value"
        />

        <DialogFooter>
          <Button
            variant="ghost"
            @click="pluginReadme.readmeDialogVisible.value = false"
          >
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

        <div v-if="pluginSettings.settingsPlugin.value" class="plugin-settings-header">
          <div class="plugin-settings-header__meta">
            <Badge v-if="pluginSettings.settingsState.value" variant="secondary">
              {{ pluginSettings.settingsState.value.section }}
            </Badge>
            <Badge v-if="pluginSettings.settingsState.value" variant="outline">
              {{ pluginSettingsSourceLabel(pluginSettings.settingsState.value.config_source) }}
            </Badge>
            <Badge
              v-if="pluginSettings.settingsPlugin.value.admin_level > 0"
              variant="secondary"
            >
              Lv.{{ pluginSettings.settingsPlugin.value.admin_level }}
            </Badge>
            <Badge variant="outline">
              {{ pluginSettings.settingsPlugin.value.plugin_type }}
            </Badge>
            <span v-if="pluginMetaSummary(pluginSettings.settingsPlugin.value)">
              {{ pluginMetaSummary(pluginSettings.settingsPlugin.value) }}
            </span>
            <span v-if="pluginSettings.settingsPlugin.value.installed_package">
              {{ t('plugins.settingsInstalledPackage') }}:
              {{ pluginSettings.settingsPlugin.value.installed_package }}
            </span>
          </div>

          <div
            v-if="pluginSettings.settingsPlugin.value.child_plugins.length > 0
              || pluginSettings.settingsPlugin.value.required_plugins.length > 0
              || pluginSettings.settingsPlugin.value.dependent_plugins.length > 0"
            class="plugin-settings-header__relations"
          >
            <Badge
              v-for="childPlugin in pluginSettings.settingsPlugin.value.child_plugins"
              :key="`settings-child:${childPlugin}`"
              variant="outline"
            >
              {{ t('plugins.childPlugins') }}: {{ childPlugin }}
            </Badge>
            <Badge
              v-for="dependency in pluginSettings.settingsPlugin.value.required_plugins"
              :key="`settings-required:${dependency}`"
              variant="outline"
            >
              {{ t('plugins.requires', { name: pluginLabel(dependency) }) }}
            </Badge>
            <Badge
              v-for="dependency in pluginSettings.settingsPlugin.value.dependent_plugins"
              :key="`settings-dependent:${dependency}`"
              variant="outline"
            >
              {{ t('plugins.requiredBy', { name: pluginLabel(dependency) }) }}
            </Badge>
          </div>

          <Alert
            v-if="pluginSettings.settingsPlugin.value.is_pending_uninstall"
            variant="destructive"
          >
            <AlertCircle :size="16" />
            <AlertDescription>{{ t('plugins.pendingUninstallDetail') }}</AlertDescription>
          </Alert>
        </div>

        <Alert v-if="pluginSettings.settingsErrorMessage.value" variant="destructive">
          <AlertCircle :size="16" />
          <AlertDescription>{{ pluginSettings.settingsErrorMessage.value }}</AlertDescription>
        </Alert>

        <LoadingSkeleton
          v-if="pluginSettings.settingsDialogLoading.value"
          rows="7"
        />

        <Tabs
          v-else
          v-model="pluginSettings.settingsEditorMode.value"
          class="plugin-settings-tabs"
        >
          <div class="plugin-settings-tabs__bar">
            <TabsList>
              <TabsTrigger value="basic">
                <FileCog :size="15" />
                {{ t('plugins.settingsBasicTab') }}
              </TabsTrigger>
              <TabsTrigger value="advanced">
                <Code2 :size="15" />
                {{ t('plugins.settingsAdvancedTab') }}
              </TabsTrigger>
            </TabsList>

            <Button
              v-if="pluginSettings.settingsEditorMode.value === 'basic'"
              :disabled="!pluginSettings.hasPendingPluginChanges.value || pluginSettings.settingsSaving.value"
              size="sm"
              @click="openPluginSettingsPreview"
            >
              <Save :size="15" />
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
                          v-model:checked="pluginSettings.settingsForm.value[field.key]"
                          :disabled="!pluginSettings.pluginEditor.isFieldEditing(field)"
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
                    <span>
                      {{ t('plugins.settingsValueSource') }}:
                      {{ pluginSettings.fieldSourceLabel(field.value_source) }}
                    </span>
                    <span v-if="field.choices.length > 0">
                      {{ t('plugins.settingsChoices') }}:
                      {{ pluginSettings.formatFieldChoices(field) }}
                    </span>
                    <span>
                      {{ t('plugins.settingsCurrent') }}:
                      {{ pluginSettings.displayFieldValue(field.current_value) }}
                    </span>
                    <span v-if="field.has_local_override">
                      {{ t('plugins.settingsLocal') }}:
                      {{ pluginSettings.displayFieldValue(field.local_value) }}
                    </span>
                  </div>
                </details>
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
          <Button
            variant="ghost"
            @click="pluginSettings.previewDialogVisible.value = false"
          >
            {{ t('common.cancel') }}
          </Button>
          <Button
            :disabled="pluginSettings.previewSaving.value"
            @click="confirmPluginSettingsPreview"
          >
            <Save :size="16" />
            {{ t('plugins.confirmSave') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <AlertDialog v-model:open="pluginMaintenance.uninstallConfirmVisible.value">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{{ t('plugins.settingsUninstall') }}</AlertDialogTitle>
          <AlertDialogDescription>
            {{ pluginMaintenance.uninstallConfirmSummary.value }}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <Alert variant="destructive">
          <AlertCircle :size="16" />
          <AlertDescription>
            {{ t('plugins.settingsRestartHint') }}
          </AlertDescription>
        </Alert>

        <div class="plugin-maintenance-checkbox">
          <Checkbox
            id="plugin-uninstall-remove-config"
            v-model:checked="pluginMaintenance.uninstallRemoveConfig.value"
          />
          <div>
            <FieldLabel for="plugin-uninstall-remove-config">
              {{ t('plugins.settingsUninstallRemoveConfig') }}
            </FieldLabel>
            <p>{{ t('plugins.settingsUninstallRemoveConfigHint') }}</p>
          </div>
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel @click="pluginMaintenance.closeUninstallConfirm">
            {{ t('common.cancel') }}
          </AlertDialogCancel>
          <AlertDialogAction
            class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            :disabled="Boolean(pluginMaintenance.uninstallingModule.value)"
            @click="confirmUninstallPlugin"
          >
            <Trash2 data-icon="inline-start" />
            {{ t('plugins.settingsUninstall') }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <AlertDialog v-model:open="pluginMaintenance.orphanConfigDialogVisible.value">
      <AlertDialogContent class="plugin-maintenance-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>{{ t('plugins.orphanConfigCleanup') }}</AlertDialogTitle>
          <AlertDialogDescription>{{ t('plugins.orphanConfigCleanupHint') }}</AlertDialogDescription>
        </AlertDialogHeader>

        <LoadingSkeleton
          v-if="pluginMaintenance.orphanConfigLoading.value"
          rows="4"
        />
        <EmptyState
          v-else-if="pluginMaintenance.orphanConfigItems.value.length === 0"
          :title="t('plugins.orphanConfigCleanupEmpty')"
        />
        <div v-else class="plugin-maintenance-list">
          <article
            v-for="item in pluginMaintenance.orphanConfigItems.value"
            :key="`${item.section}:${item.module_name || ''}`"
            class="plugin-maintenance-list__item"
          >
            <div>
              <strong>[plugins.{{ item.section }}]</strong>
              <span>{{ item.module_name || t('plugins.orphanConfigNoModule') }}</span>
            </div>
            <p>{{ item.reason }}</p>
          </article>
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel @click="pluginMaintenance.orphanConfigDialogVisible.value = false">
            {{ t('common.cancel') }}
          </AlertDialogCancel>
          <AlertDialogAction
            class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            :disabled="pluginMaintenance.orphanConfigItems.value.length === 0 || pluginMaintenance.orphanConfigCleaning.value"
            @click="confirmCleanupOrphanConfigs"
          >
            <Trash2 data-icon="inline-start" />
            {{ t('plugins.orphanConfigCleanupAction') }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <Dialog v-model:open="pluginMaintenance.manualInstallDialogVisible.value">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ t('plugins.manualInstall') }}</DialogTitle>
          <DialogDescription>{{ t('plugins.manualInstallHint') }}</DialogDescription>
        </DialogHeader>

        <FieldGroup class="plugin-maintenance-form">
          <Field>
            <FieldLabel for="plugin-manual-source">
              {{ t('plugins.manualInstallSourceType') }}
            </FieldLabel>
            <Select v-model="pluginMaintenance.manualInstallSourceType.value">
              <SelectTrigger id="plugin-manual-source">
                <SelectValue :placeholder="t('plugins.manualInstallSourceType')" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem
                    v-for="option in pluginMaintenance.manualInstallSourceOptions.value"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>

          <Field>
            <FieldLabel for="plugin-manual-requirement">
              {{ pluginMaintenance.manualInstallRequirementLabel.value }}
            </FieldLabel>
            <Input
              id="plugin-manual-requirement"
              v-model.trim="pluginMaintenance.manualInstallRequirement.value"
            />
            <FieldDescription>
              {{ pluginMaintenance.manualInstallRequirementHint.value }}
            </FieldDescription>
          </Field>

          <Field>
            <FieldLabel for="plugin-manual-module">
              {{ t('plugins.manualInstallModule') }}
            </FieldLabel>
            <Input
              id="plugin-manual-module"
              v-model.trim="pluginMaintenance.manualInstallModuleName.value"
            />
            <FieldDescription>{{ t('plugins.manualInstallModuleHint') }}</FieldDescription>
          </Field>
        </FieldGroup>

        <DialogFooter>
          <Button
            variant="ghost"
            @click="pluginMaintenance.manualInstallDialogVisible.value = false"
          >
            {{ t('common.cancel') }}
          </Button>
          <Button
            :disabled="!pluginMaintenance.canSubmitManualInstall.value || pluginMaintenance.manualInstallSubmitting.value"
            @click="submitManualInstall"
          >
            <UploadCloud :size="16" />
            {{ t('plugins.manualInstallSubmit') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <TaskDialog
      v-model="pluginMaintenance.manualInstallTaskDialogVisible.value"
      :binding-value="pluginMaintenance.manualInstallTask.value?.binding_value"
      :close-label="t('common.close')"
      :current-phase="pluginMaintenance.manualInstallTask.value?.current_phase"
      :current-phase-label="pluginMaintenance.manualInstallTask.value?.current_phase_label"
      :diagnostics="pluginMaintenance.manualInstallTask.value?.diagnostics || []"
      :loading="pluginMaintenance.manualInstallTaskRunning.value"
      :logs="pluginMaintenance.manualInstallTask.value?.logs || ''"
      :operation="pluginMaintenance.manualInstallTask.value?.operation"
      :queue-position="pluginMaintenance.manualInstallTask.value?.queue_position"
      :requirement="pluginMaintenance.manualInstallTask.value?.requirement"
      :resource-kind="pluginMaintenance.manualInstallTask.value?.resource_kind"
      :restart-required="pluginMaintenance.manualInstallTask.value?.restart_required"
      :status="pluginMaintenance.manualInstallTaskStatusLabel.value"
      :status-tone="pluginMaintenance.manualInstallTaskStatusTone.value"
      :steps="pluginMaintenance.manualInstallTask.value?.steps || []"
      :title="pluginMaintenance.manualInstallTask.value?.title || t('plugins.manualInstallTaskTitle')"
      :waiting-text="t('plugins.manualInstallWaiting')"
    >
      <template v-if="pluginMaintenance.manualInstallTaskErrorSummary.value" #details>
        <Alert variant="destructive">
          <AlertCircle :size="16" />
          <AlertDescription>
            {{ pluginMaintenance.manualInstallTaskErrorSummary.value }}
          </AlertDescription>
        </Alert>
      </template>
    </TaskDialog>

    <TaskDialog
      v-model="pluginMaintenance.packageUpdateTaskDialogVisible.value"
      :binding-value="pluginMaintenance.packageUpdateTask.value?.binding_value"
      :close-label="t('common.close')"
      :current-phase="pluginMaintenance.packageUpdateTask.value?.current_phase"
      :current-phase-label="pluginMaintenance.packageUpdateTask.value?.current_phase_label"
      :diagnostics="pluginMaintenance.packageUpdateTask.value?.diagnostics || []"
      :loading="pluginMaintenance.packageUpdateTaskRunning.value"
      :logs="pluginMaintenance.packageUpdateTask.value?.logs || ''"
      :operation="pluginMaintenance.packageUpdateTask.value?.operation"
      :queue-position="pluginMaintenance.packageUpdateTask.value?.queue_position"
      :requirement="pluginMaintenance.packageUpdateTask.value?.requirement"
      :resource-kind="pluginMaintenance.packageUpdateTask.value?.resource_kind"
      :restart-required="pluginMaintenance.packageUpdateTask.value?.restart_required"
      :status="pluginMaintenance.packageUpdateTaskStatusLabel.value"
      :status-tone="pluginMaintenance.packageUpdateTaskStatusTone.value"
      :steps="pluginMaintenance.packageUpdateTask.value?.steps || []"
      :title="pluginMaintenance.packageUpdateTask.value?.title || t('plugins.packageUpdateTaskTitle')"
      :waiting-text="t('plugins.packageUpdateWaiting')"
    >
      <template v-if="pluginMaintenance.packageUpdateTaskErrorSummary.value" #details>
        <Alert variant="destructive">
          <AlertCircle :size="16" />
          <AlertDescription>
            {{ pluginMaintenance.packageUpdateTaskErrorSummary.value }}
          </AlertDescription>
        </Alert>
      </template>
    </TaskDialog>
  </PageScaffold>
</template>
