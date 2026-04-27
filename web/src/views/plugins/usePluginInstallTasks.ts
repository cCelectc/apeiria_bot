import type { PluginItem, PluginStoreTask } from '@/api/plugins'
import type { RestartPendingEntry } from '@/stores/restart'
import type { PluginTranslate } from '@/views/plugins/display'
import { computed, ref } from 'vue'
import { getErrorMessage } from '@/api/client'
import {
  getPluginInstallTask,
  installManualPlugin,
  updateInstalledPlugin,
} from '@/api/plugins'
import {
  manualInstallRequirementHint as buildManualInstallRequirementHint,
  manualInstallRequirementLabel as buildManualInstallRequirementLabel,
  manualInstallSourceOptions as buildManualInstallSourceOptions,
  canSubmitManualInstall as canSubmitManualInstallRequirement,
  type ManualInstallSourceType,
} from '@/views/plugins/install'
import {
  manualInstallTaskStatusLabel as buildManualInstallTaskStatusLabel,
  packageUpdateTaskStatusLabel as buildPackageUpdateTaskStatusLabel,
  summarizeTaskError,
} from '@/views/plugins/tasks'

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

interface RestartStoreLike {
  markPending: (entry: Omit<RestartPendingEntry, 'updated_at'>) => void
}

export function usePluginInstallTasks (options: {
  loadPluginManagement: (options?: { forceUpdateRefresh?: boolean }) => Promise<void>
  noticeStore: NoticeStoreLike
  restartStore: RestartStoreLike
  t: PluginTranslate
}) {
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
    canSubmitManualInstallRequirement(manualInstallRequirement.value),
  )
  const manualInstallTaskErrorSummary = computed(() => {
    return summarizeTaskError(manualInstallTask.value?.error)
  })
  const manualInstallTaskStatusLabel = computed(() => {
    return buildManualInstallTaskStatusLabel(manualInstallTask.value, options.t)
  })
  const packageUpdateTaskErrorSummary = computed(() => {
    return summarizeTaskError(packageUpdateTask.value?.error)
  })
  const packageUpdateTaskStatusLabel = computed(() => {
    return buildPackageUpdateTaskStatusLabel(packageUpdateTask.value, options.t)
  })

  function openManualInstallDialog () {
    manualInstallSourceType.value = 'pypi'
    manualInstallRequirement.value = ''
    manualInstallModuleName.value = ''
    manualInstallDialogVisible.value = true
  }

  async function submitManualInstall () {
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

  function stopManualInstallTaskPolling () {
    if (manualInstallTaskPollTimer !== null) {
      window.clearInterval(manualInstallTaskPollTimer)
      manualInstallTaskPollTimer = null
    }
  }

  function stopPackageUpdateTaskPolling () {
    if (packageUpdateTaskPollTimer !== null) {
      window.clearInterval(packageUpdateTaskPollTimer)
      packageUpdateTaskPollTimer = null
    }
  }

  function startManualInstallTaskPolling (taskId: string) {
    stopManualInstallTaskPolling()
    manualInstallTaskPollTimer = window.setInterval(async () => {
      try {
        const response = await getPluginInstallTask(taskId)
        manualInstallTask.value = response.data
        if (response.data.status === 'succeeded' || response.data.status === 'failed') {
          stopManualInstallTaskPolling()
          if (response.data.status === 'succeeded') {
            const moduleName = typeof response.data.result.module_name === 'string'
              ? response.data.result.module_name
              : ''
            const requirement = typeof response.data.result.requirement === 'string'
              ? response.data.result.requirement
              : activeManualInstallRequirement.value
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
            void options.loadPluginManagement()
          } else {
            options.noticeStore.show(
              summarizeTaskError(response.data.error)
              || options.t('plugins.manualInstallFailed'),
              'error',
            )
          }
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

  function startPackageUpdateTaskPolling (taskId: string) {
    stopPackageUpdateTaskPolling()
    packageUpdateTaskPollTimer = window.setInterval(async () => {
      try {
        const response = await getPluginInstallTask(taskId)
        packageUpdateTask.value = response.data
        if (response.data.status === 'succeeded' || response.data.status === 'failed') {
          stopPackageUpdateTaskPolling()
          if (response.data.status === 'succeeded') {
            const moduleName = typeof response.data.result.module_name === 'string'
              ? response.data.result.module_name
              : packageUpdatingModule.value
            const requirement = typeof response.data.result.requirement === 'string'
              ? response.data.result.requirement
              : ''
            options.restartStore.markPending({
              id: `plugin-package-update:${moduleName || requirement}`,
              scope: 'plugins',
              summary: options.t('plugins.packageUpdateRestartPending', {
                name: moduleName || requirement,
              }),
            })
            options.noticeStore.show(options.t('plugins.packageUpdateSucceeded'), 'success')
            void options.loadPluginManagement({ forceUpdateRefresh: true })
          } else {
            options.noticeStore.show(
              summarizeTaskError(response.data.error)
              || options.t('plugins.packageUpdateFailed'),
              'error',
            )
          }
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

  async function updatePluginItem (item: PluginItem) {
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

  return {
    canSubmitManualInstall,
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
    manualInstallTaskStatusLabel,
    openManualInstallDialog,
    packageUpdateTask,
    packageUpdateTaskDialogVisible,
    packageUpdateTaskErrorSummary,
    packageUpdateTaskStatusLabel,
    packageUpdatingModule,
    stopManualInstallTaskPolling,
    stopPackageUpdateTaskPolling,
    submitManualInstall,
    updatePluginItem,
  }
}
