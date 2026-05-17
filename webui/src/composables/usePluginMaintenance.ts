import type {
  OrphanPluginConfigItem,
  PluginItem,
  PluginStoreTask,
  PluginUpdateCheckItem,
} from '@/api/plugins'
import { computed, onBeforeUnmount, ref } from 'vue'
import { getErrorMessage } from '@/api/client'
import {
  checkPluginUpdates,
  cleanupOrphanPluginConfigs,
  getOrphanPluginConfigs,
  getPluginInstallTask,
  installManualPlugin,
  uninstallPlugin,
  updateInstalledPlugin,
} from '@/api/plugins'
import type { RestartPendingEntry } from '@/stores/restart'
import {
  canSubmitManualInstall as canSubmitManualInstallTarget,
  canUpdatePlugin as canUpdatePluginForRole,
  canUninstallPlugin as canUninstallPluginForRole,
  hasPluginUpdate as hasPluginUpdateForChecks,
  manualInstallRequirementHint as buildManualInstallRequirementHint,
  manualInstallRequirementLabel as buildManualInstallRequirementLabel,
  manualInstallSourceOptions as buildManualInstallSourceOptions,
  manualInstallTaskStatusLabel as buildManualInstallTaskStatusLabel,
  packageUpdateTaskStatusLabel as buildPackageUpdateTaskStatusLabel,
  summarizeTaskError,
  type ManualInstallSourceType,
  uninstallConfirmSummary as buildUninstallConfirmSummary,
  updateButtonTooltip as buildUpdateButtonTooltip,
} from '@/utils/pluginDisplay'

type PluginTranslate = (key: string, params?: Record<string, unknown>) => string

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

interface RestartStoreLike {
  markPending: (entry: Omit<RestartPendingEntry, 'updated_at'>) => void
}

export function usePluginMaintenance(options: {
  loadPluginManagement: (options?: { forceUpdateRefresh?: boolean }) => Promise<void>
  noticeStore: NoticeStoreLike
  restartStore: RestartStoreLike
  t: PluginTranslate
}) {
  const updateCheckLoading = ref(false)
  const pluginUpdateChecks = ref<Record<string, PluginUpdateCheckItem>>({})

  const manualInstallDialogVisible = ref(false)
  const manualInstallTaskDialogVisible = ref(false)
  const manualInstallSubmitting = ref(false)
  const manualInstallSourceType = ref<ManualInstallSourceType>('pypi')
  const manualInstallRequirement = ref('')
  const manualInstallModuleName = ref('')
  const manualInstallTask = ref<PluginStoreTask | null>(null)
  const activeManualInstallRequirement = ref('')
  let manualInstallTaskPollTimer: number | null = null

  const packageUpdateTaskDialogVisible = ref(false)
  const packageUpdateTask = ref<PluginStoreTask | null>(null)
  const packageUpdatingModule = ref('')
  let packageUpdateTaskPollTimer: number | null = null

  const uninstallingModule = ref('')
  const uninstallConfirmVisible = ref(false)
  const uninstallConfirmItem = ref<PluginItem | null>(null)
  const uninstallRemoveConfig = ref(false)

  const orphanConfigDialogVisible = ref(false)
  const orphanConfigLoading = ref(false)
  const orphanConfigCleaning = ref(false)
  const orphanConfigItems = ref<OrphanPluginConfigItem[]>([])

  const manualInstallSourceOptions = computed(() =>
    buildManualInstallSourceOptions(options.t),
  )
  const manualInstallRequirementLabel = computed(() =>
    buildManualInstallRequirementLabel(manualInstallSourceType.value, options.t),
  )
  const manualInstallRequirementHint = computed(() =>
    buildManualInstallRequirementHint(manualInstallSourceType.value, options.t),
  )
  const canSubmitManualInstall = computed(() =>
    canSubmitManualInstallTarget(manualInstallRequirement.value),
  )
  const manualInstallTaskErrorSummary = computed(() =>
    summarizeTaskError(manualInstallTask.value?.error),
  )
  const manualInstallTaskStatusLabel = computed(() =>
    buildManualInstallTaskStatusLabel(manualInstallTask.value, options.t),
  )
  const manualInstallTaskRunning = computed(() =>
    manualInstallTask.value?.status === 'pending'
    || manualInstallTask.value?.status === 'queued'
    || manualInstallTask.value?.status === 'running',
  )
  const manualInstallTaskStatusTone = computed(() =>
    taskStatusTone(manualInstallTask.value),
  )
  const packageUpdateTaskErrorSummary = computed(() =>
    summarizeTaskError(packageUpdateTask.value?.error),
  )
  const packageUpdateTaskStatusLabel = computed(() =>
    buildPackageUpdateTaskStatusLabel(packageUpdateTask.value, options.t),
  )
  const packageUpdateTaskRunning = computed(() =>
    packageUpdateTask.value?.status === 'pending'
    || packageUpdateTask.value?.status === 'queued'
    || packageUpdateTask.value?.status === 'running',
  )
  const packageUpdateTaskStatusTone = computed(() =>
    taskStatusTone(packageUpdateTask.value),
  )
  const uninstallConfirmSummary = computed(() =>
    buildUninstallConfirmSummary(uninstallConfirmItem.value, options.t),
  )

  async function runPluginUpdateCheck(forceRefresh = false) {
    if (updateCheckLoading.value) {
      return
    }
    updateCheckLoading.value = true
    try {
      const response = await checkPluginUpdates({
        force_refresh: forceRefresh || undefined,
      })
      pluginUpdateChecks.value = Object.fromEntries(
        response.data.map(item => [item.module_name, item]),
      )
    } catch (error) {
      options.noticeStore.show(
        getErrorMessage(error, options.t('plugins.updateCheckFailed')),
        'error',
      )
    } finally {
      updateCheckLoading.value = false
    }
  }

  function hasPluginUpdate(item: PluginItem) {
    return hasPluginUpdateForChecks(pluginUpdateChecks.value, item)
  }

  function updateButtonTooltip(item: PluginItem) {
    return buildUpdateButtonTooltip(
      pluginUpdateChecks.value,
      item,
      updateCheckLoading.value,
      options.t,
    )
  }

  function canUninstallPlugin(role: string | null | undefined, item: PluginItem) {
    return canUninstallPluginForRole(role, item)
  }

  function canUpdatePlugin(role: string | null | undefined, item: PluginItem) {
    return canUpdatePluginForRole(role, item)
  }

  function openManualInstallDialog() {
    manualInstallSourceType.value = 'pypi'
    manualInstallRequirement.value = ''
    manualInstallModuleName.value = ''
    manualInstallDialogVisible.value = true
  }

  async function submitManualInstall() {
    const requirement = manualInstallRequirement.value.trim()
    if (!requirement) {
      return
    }

    manualInstallSubmitting.value = true
    try {
      const response = await installManualPlugin({
        requirement,
        module_name: manualInstallModuleName.value.trim() || undefined,
      })
      activeManualInstallRequirement.value = requirement
      manualInstallTask.value = response.data
      manualInstallDialogVisible.value = false
      manualInstallTaskDialogVisible.value = true
      startManualInstallTaskPolling(response.data.task_id)
    } catch (error) {
      options.noticeStore.show(
        getErrorMessage(error, options.t('plugins.manualInstallFailed')),
        'error',
      )
    } finally {
      manualInstallSubmitting.value = false
    }
  }

  async function updatePluginItem(item: PluginItem) {
    if (!item.installed_package || packageUpdatingModule.value) {
      return
    }
    packageUpdatingModule.value = item.module_name
    try {
      const response = await updateInstalledPlugin(item.module_name, {
        package_name: item.installed_package,
      })
      packageUpdateTask.value = response.data
      packageUpdateTaskDialogVisible.value = true
      startPackageUpdateTaskPolling(response.data.task_id)
    } catch (error) {
      packageUpdatingModule.value = ''
      options.noticeStore.show(
        getErrorMessage(error, options.t('plugins.packageUpdateFailed')),
        'error',
      )
    }
  }

  function openUninstallConfirm(item: PluginItem) {
    uninstallConfirmItem.value = item
    uninstallRemoveConfig.value = false
    uninstallConfirmVisible.value = true
  }

  function closeUninstallConfirm() {
    uninstallConfirmVisible.value = false
    uninstallConfirmItem.value = null
    uninstallRemoveConfig.value = false
  }

  async function confirmUninstallPlugin() {
    if (!uninstallConfirmItem.value) {
      return
    }
    const item = uninstallConfirmItem.value
    uninstallingModule.value = item.module_name
    try {
      await uninstallPlugin(item.module_name, {
        remove_config: uninstallRemoveConfig.value,
      })
      options.restartStore.markPending({
        id: `plugin-uninstall:${item.module_name}`,
        scope: 'plugins',
        summary: options.t('restart.pendingPluginUninstall', {
          name: item.name || item.module_name,
        }),
      })
      options.noticeStore.show(options.t('plugins.settingsUninstallSucceeded'), 'success')
      closeUninstallConfirm()
      await options.loadPluginManagement()
    } catch (error) {
      options.noticeStore.show(
        getErrorMessage(error, options.t('plugins.settingsUninstallFailed')),
        'error',
      )
    } finally {
      uninstallingModule.value = ''
    }
  }

  async function openOrphanConfigDialog() {
    orphanConfigDialogVisible.value = true
    orphanConfigLoading.value = true
    try {
      orphanConfigItems.value = (await getOrphanPluginConfigs()).data.items
    } catch (error) {
      orphanConfigDialogVisible.value = false
      options.noticeStore.show(
        getErrorMessage(error, options.t('plugins.orphanConfigCleanupFailed')),
        'error',
      )
    } finally {
      orphanConfigLoading.value = false
    }
  }

  async function confirmCleanupOrphanConfigs() {
    orphanConfigCleaning.value = true
    try {
      const removed = (await cleanupOrphanPluginConfigs()).data.items
      orphanConfigItems.value = removed
      orphanConfigDialogVisible.value = false
      if (removed.length > 0) {
        options.noticeStore.show(
          options.t('plugins.orphanConfigCleanupSucceeded', { count: removed.length }),
          'success',
        )
      } else {
        options.noticeStore.show(options.t('plugins.orphanConfigCleanupEmpty'), 'info')
      }
      await options.loadPluginManagement()
    } catch (error) {
      options.noticeStore.show(
        getErrorMessage(error, options.t('plugins.orphanConfigCleanupFailed')),
        'error',
      )
    } finally {
      orphanConfigCleaning.value = false
    }
  }

  function startManualInstallTaskPolling(taskId: string) {
    stopManualInstallTaskPolling()
    manualInstallTaskPollTimer = window.setInterval(async () => {
      try {
        const response = await getPluginInstallTask(taskId)
        manualInstallTask.value = response.data
        if (isTerminalTask(response.data)) {
          stopManualInstallTaskPolling()
          handleManualInstallTaskResult(response.data)
        }
      } catch (error) {
        stopManualInstallTaskPolling()
        options.noticeStore.show(
          getErrorMessage(error, options.t('plugins.manualInstallFailed')),
          'error',
        )
      }
    }, 1500)
  }

  function handleManualInstallTaskResult(task: PluginStoreTask) {
    if (task.status === 'succeeded') {
      const moduleName = stringResult(task, 'module_name')
      const requirement = stringResult(task, 'requirement')
        || activeManualInstallRequirement.value
      options.restartStore.markPending({
        id: `plugin-manual-install:${moduleName || requirement}`,
        scope: 'plugins',
        summary: options.t('plugins.manualInstallRestartPending', {
          name: moduleName || requirement,
        }),
        undo: {
          kind: 'plugin-install',
          packageName: requirement,
          moduleName,
        },
      })
      options.noticeStore.show(options.t('plugins.manualInstallSucceeded'), 'success')
      void options.loadPluginManagement({ forceUpdateRefresh: true })
      return
    }

    options.noticeStore.show(
      summarizeTaskError(task.error) || options.t('plugins.manualInstallFailed'),
      'error',
    )
  }

  function startPackageUpdateTaskPolling(taskId: string) {
    stopPackageUpdateTaskPolling()
    packageUpdateTaskPollTimer = window.setInterval(async () => {
      try {
        const response = await getPluginInstallTask(taskId)
        packageUpdateTask.value = response.data
        if (isTerminalTask(response.data)) {
          stopPackageUpdateTaskPolling()
          handlePackageUpdateTaskResult(response.data)
          packageUpdatingModule.value = ''
        }
      } catch (error) {
        stopPackageUpdateTaskPolling()
        packageUpdatingModule.value = ''
        options.noticeStore.show(
          getErrorMessage(error, options.t('plugins.packageUpdateFailed')),
          'error',
        )
      }
    }, 1500)
  }

  function handlePackageUpdateTaskResult(task: PluginStoreTask) {
    if (task.status === 'succeeded') {
      const moduleName = stringResult(task, 'module_name') || packageUpdatingModule.value
      const requirement = stringResult(task, 'requirement')
      options.restartStore.markPending({
        id: `plugin-package-update:${moduleName || requirement}`,
        scope: 'plugins',
        summary: options.t('plugins.packageUpdateRestartPending', {
          name: moduleName || requirement,
        }),
      })
      options.noticeStore.show(options.t('plugins.packageUpdateSucceeded'), 'success')
      void options.loadPluginManagement({ forceUpdateRefresh: true })
      return
    }

    options.noticeStore.show(
      summarizeTaskError(task.error) || options.t('plugins.packageUpdateFailed'),
      'error',
    )
  }

  function stopManualInstallTaskPolling() {
    if (manualInstallTaskPollTimer !== null) {
      window.clearInterval(manualInstallTaskPollTimer)
      manualInstallTaskPollTimer = null
    }
  }

  function stopPackageUpdateTaskPolling() {
    if (packageUpdateTaskPollTimer !== null) {
      window.clearInterval(packageUpdateTaskPollTimer)
      packageUpdateTaskPollTimer = null
    }
  }

  onBeforeUnmount(() => {
    stopManualInstallTaskPolling()
    stopPackageUpdateTaskPolling()
  })

  return {
    canSubmitManualInstall,
    canUninstallPlugin,
    canUpdatePlugin,
    closeUninstallConfirm,
    confirmCleanupOrphanConfigs,
    confirmUninstallPlugin,
    hasPluginUpdate,
    manualInstallDialogVisible,
    manualInstallModuleName,
    manualInstallRequirement,
    manualInstallRequirementHint,
    manualInstallRequirementLabel,
    manualInstallSourceOptions,
    manualInstallSourceType,
    manualInstallSubmitting,
    manualInstallTask,
    manualInstallTaskDialogVisible,
    manualInstallTaskErrorSummary,
    manualInstallTaskRunning,
    manualInstallTaskStatusLabel,
    manualInstallTaskStatusTone,
    openManualInstallDialog,
    openOrphanConfigDialog,
    openUninstallConfirm,
    orphanConfigCleaning,
    orphanConfigDialogVisible,
    orphanConfigItems,
    orphanConfigLoading,
    packageUpdateTask,
    packageUpdateTaskDialogVisible,
    packageUpdateTaskErrorSummary,
    packageUpdateTaskRunning,
    packageUpdateTaskStatusLabel,
    packageUpdateTaskStatusTone,
    packageUpdatingModule,
    pluginUpdateChecks,
    runPluginUpdateCheck,
    submitManualInstall,
    uninstallConfirmItem,
    uninstallConfirmSummary,
    uninstallConfirmVisible,
    uninstallRemoveConfig,
    uninstallingModule,
    updateButtonTooltip,
    updateCheckLoading,
    updatePluginItem,
  }
}

function isTerminalTask(task: PluginStoreTask) {
  return task.status === 'succeeded' || task.status === 'failed'
}

function stringResult(task: PluginStoreTask, key: string) {
  const value = task.result[key]
  return typeof value === 'string' ? value : ''
}

function taskStatusTone(task: PluginStoreTask | null) {
  if (task?.status === 'failed') {
    return 'error' as const
  }
  if (task?.status === 'succeeded') {
    return 'success' as const
  }
  return 'info' as const
}
