<script setup lang="ts">
import type { DriverConfigItem } from '@/api/core'
import type { RawSettingsResponse } from '@/api/settings'
import type { SettingField } from '@/utils/settingsEditor'
import {
  AlertCircle,
  Cable,
  CheckCircle2,
  Code2,
  Eye,
  FileCog,
  PackageOpen,
  Plus,
  RefreshCw,
  Save,
  SlidersHorizontal,
  Trash2,
  Wrench,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
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
} from '@/components/management'
import type { WorkbenchMetricItem, WorkbenchTone } from '@/components/management'
import { SettingsFieldEditor } from '@/components/settings'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
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
import { useAdapterManagement } from '@/composables/useAdapterManagement'
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

const { t } = useI18n()
const router = useRouter()
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
  adapterManager.configuredModules.value.filter(item => item.is_loaded).length,
)
const unavailableAdapterCount = computed(() =>
  adapterManager.configuredModules.value.filter(item => !item.is_importable).length,
)
const activeDriverCount = computed(() =>
  driverBuiltin.value.filter(item => item.is_active).length,
)
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
      total: adapterManager.adapterCount.value,
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

async function refreshCorePage() {
  loading.value = true
  errorMessage.value = ''
  try {
    await Promise.all([
      coreEditor.reload(),
      adapterManager.reload(),
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

function openAdapterConfigWithNewRow() {
  if (adapterManager.draftRows.value.length === 0) {
    adapterManager.addDraftRow()
  }
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

function adapterDisplayName(moduleName: string) {
  return moduleName.split('.').at(-1) || moduleName
}

function adapterTone(item: { is_loaded: boolean, is_importable: boolean }): WorkbenchTone {
  if (!item.is_importable) {
    return 'warning'
  }
  return item.is_loaded ? 'success' : 'default'
}

function driverTone(item: DriverConfigItem): WorkbenchTone {
  return item.is_active ? 'success' : 'warning'
}

function driverStatusText(item: DriverConfigItem) {
  return item.is_active ? t('plugins.driverActive') : t('plugins.driverRegisteredOnly')
}

function openPackageManager() {
  void router.push({ name: 'adapter-store' })
}

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
      <Button :disabled="loading" variant="secondary" @click="refreshCorePage">
        <RefreshCw :class="{ 'animate-spin': loading }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" />

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

      <TabsContent value="adapters">
        <Panel
          :subtitle="t('core.adapterConfigDescription')"
          :title="t('core.adaptersTab')"
        >
          <template #actions>
            <Badge variant="secondary">
              {{ t('plugins.adapterCount') }}: {{ adapterManager.adapterCount.value }}
            </Badge>
            <Button variant="secondary" @click="adapterConfigDialogVisible = true">
              <SlidersHorizontal :size="16" />
              {{ t('core.adapterOverviewAdvancedAction') }}
            </Button>
            <Button variant="outline" @click="openPackageManager">
              <PackageOpen :size="16" />
              {{ t('core.adapterPackageManager') }}
            </Button>
          </template>

          <Alert v-if="adapterManager.errorMessage.value" variant="destructive">
            <AlertCircle :size="16" />
            <AlertDescription>{{ adapterManager.errorMessage.value }}</AlertDescription>
          </Alert>

          <LoadingSkeleton v-if="adapterManager.loading.value" rows="5" />

          <div v-else-if="adapterManager.configuredModules.value.length > 0" class="adapter-overview">
            <div class="adapter-overview-strip">
              <div class="adapter-overview-strip__item">
                <Cable :size="20" />
                <div>
                  <div class="adapter-overview-strip__title">
                    {{ t('core.adapterOverviewRuntimeTitle') }}
                  </div>
                  <div class="adapter-overview-strip__value">
                    {{ t('core.adapterOverviewRuntimeValue', { loaded: loadedAdapterCount, total: adapterManager.adapterCount.value }) }}
                  </div>
                  <div class="adapter-overview-strip__text">
                    {{ t('core.adapterOverviewRuntimeText') }}
                  </div>
                </div>
              </div>

              <div class="adapter-overview-strip__item">
                <Code2 :size="20" />
                <div>
                  <div class="adapter-overview-strip__title">
                    {{ t('core.adapterOverviewConfigTitle') }}
                  </div>
                  <div class="adapter-overview-strip__value">
                    {{ t('core.adapterOverviewConfigValue', { total: adapterManager.adapterCount.value }) }}
                  </div>
                  <div class="adapter-overview-strip__text">
                    {{ t('core.adapterOverviewConfigText') }}
                  </div>
                </div>
              </div>

              <div class="adapter-overview-strip__item" :class="{ 'adapter-overview-strip__item--warning': unavailableAdapterCount > 0 }">
                <AlertCircle :size="20" />
                <div>
                  <div class="adapter-overview-strip__title">
                    {{ t('core.adapterOverviewRestartTitle') }}
                  </div>
                  <div class="adapter-overview-strip__value">
                    {{
                      unavailableAdapterCount > 0
                        ? t('core.adapterOverviewUnavailableValue', { total: unavailableAdapterCount })
                        : t('core.adapterOverviewRestartValue')
                    }}
                  </div>
                  <div class="adapter-overview-strip__text">
                    {{ t('core.adapterOverviewRestartText') }}
                  </div>
                </div>
              </div>
            </div>

            <section class="adapter-status-list" :aria-label="t('core.adapterOverviewListTitle')">
              <div class="adapter-status-list__header">
                <div>
                  <div class="adapter-status-list__title">
                    {{ t('core.adapterOverviewListTitle') }}
                  </div>
                  <div class="adapter-status-list__description">
                    {{ t('core.adapterOverviewListDescription') }}
                  </div>
                </div>
              </div>

              <article
                v-for="item in adapterManager.configuredModules.value"
                :key="item.name"
                class="adapter-status-row"
              >
                <div class="adapter-status-row__signal" :class="`workbench-tone--${adapterTone(item)}`">
                  <CheckCircle2 v-if="item.is_loaded" :size="18" />
                  <AlertCircle v-else :size="18" />
                </div>
                <div class="adapter-status-row__main">
                  <div class="adapter-status-row__title-line">
                    <h2 class="adapter-status-row__title">
                      {{ adapterDisplayName(item.name) }}
                    </h2>
                    <div class="adapter-status-row__chips">
                      <StatusBadge
                        :label="item.is_loaded ? t('core.adapterLoaded') : t('core.adapterNotLoaded')"
                        :tone="item.is_loaded ? 'success' : 'default'"
                      />
                      <StatusBadge
                        :label="item.is_importable ? t('core.adapterImportable') : t('core.adapterUnavailable')"
                        :tone="item.is_importable ? 'success' : 'warning'"
                      />
                    </div>
                  </div>
                  <div class="adapter-status-row__module">
                    {{ item.name }}
                  </div>
                  <div class="adapter-status-row__summary">
                    {{ adapterManager.rowStatusSummary(item.name) }}
                  </div>
                </div>
              </article>
            </section>
          </div>

          <EmptyState
            v-else
            :text="t('core.adapterEmptyText')"
            :title="t('plugins.emptyAdapterModules')"
          >
            <template #actions>
              <Button variant="secondary" @click="openAdapterConfigWithNewRow">
                <Plus :size="16" />
                {{ t('core.adapterOverviewEmptyAction') }}
              </Button>
              <Button variant="ghost" @click="openPackageManager">
                <PackageOpen :size="16" />
                {{ t('core.adapterPackageManager') }}
              </Button>
            </template>
          </EmptyState>
        </Panel>
      </TabsContent>

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

    <Dialog v-model:open="adapterConfigDialogVisible">
      <DialogContent class="adapter-config-dialog">
        <DialogHeader>
          <DialogTitle>{{ t('core.adapterOverviewAdvancedAction') }}</DialogTitle>
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
  </PageScaffold>
</template>
