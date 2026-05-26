import type {
  AdapterSelectionItem,
  AdapterSelectionResponse,
  AdapterStoreTask,
} from '@/api/adapters'
import type { RestartPendingEntry } from '@/stores/restart'
import { computed, onBeforeUnmount, ref } from 'vue'
import {
  disableAdapterSelection,
  enableAdapterSelection,
  getAdapterSelection,
  getAdapterStoreTask,
  installAdapterStoreItem,
  installManualAdapter,
  uninstallAdapterStoreItem,
  updateAdapterStoreItem,
} from '@/api/adapters'
import { getErrorMessage } from '@/api/client'
import { taskStatusTone as resolveTaskStatusTone } from '@/utils/feedbackState'

type AdapterSelectionTranslate = (
  key: string,
  params?: Record<string, unknown>,
) => string

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

interface RestartStoreLike {
  markPending: (entry: Omit<RestartPendingEntry, 'updated_at'>) => void
}

type AdapterTaskMode = 'install' | 'manual-install' | 'update' | 'uninstall'

const pageSize = 100

function candidateSelectionKey(item: Pick<AdapterSelectionItem, 'source_id' | 'module_name'>) {
  return `${item.source_id || 'local'}:${item.module_name}`
}

export function useAdapterSelection(options: {
  noticeStore: NoticeStoreLike
  restartStore: RestartStoreLike
  t: AdapterSelectionTranslate
}) {
  const loading = ref(false)
  const popupLoading = ref(false)
  const actionPending = ref(false)
  const taskDialogVisible = ref(false)
  const popupVisible = ref(false)
  const manualExpanded = ref(false)
  const errorMessage = ref('')
  const popupErrorMessage = ref('')
  const selection = ref<AdapterSelectionResponse | null>(null)
  const selectedCandidateKey = ref('')
  const search = ref('')
  const unenabledOnly = ref(true)
  const currentPage = ref(1)
  const activeTask = ref<AdapterStoreTask | null>(null)
  const activeItem = ref<AdapterSelectionItem | null>(null)
  const taskMode = ref<AdapterTaskMode>('install')
  const manualRequirement = ref('')
  const manualModuleName = ref('')
  let searchTimer: number | null = null
  let taskPollTimer: number | null = null

  const enabledAdapters = computed(() => selection.value?.enabled_adapters ?? [])
  const candidates = computed(() => selection.value?.candidates ?? [])
  const summary = computed(() => selection.value?.summary ?? {
    enabled: 0,
    loaded: 0,
    restart_required: 0,
    unavailable: 0,
  })
  const selectedCandidate = computed(() =>
    candidates.value.find(item =>
      candidateSelectionKey(item) === selectedCandidateKey.value,
    )
    ?? candidates.value[0]
    ?? null,
  )
  const taskIsRunning = computed(() =>
    activeTask.value?.status === 'pending'
    || activeTask.value?.status === 'queued'
    || activeTask.value?.status === 'running',
  )
  const canSubmitManualInstall = computed(() =>
    manualRequirement.value.trim().length > 0,
  )
  const taskFailed = computed(() => activeTask.value?.status === 'failed')
  const canRetryTask = computed(() =>
    taskFailed.value
    && (
      taskMode.value === 'manual-install'
        ? canSubmitManualInstall.value
        : activeItem.value !== null
    ),
  )
  const taskStatusTone = computed(() =>
    resolveTaskStatusTone(activeTask.value?.status),
  )
  const taskStatusLabel = computed(() => {
    const status = activeTask.value?.status || ''
    const prefix = taskMessagePrefix()
    if (status === 'pending' || status === 'queued') {
      return options.t(`adapterStore.${prefix}Pending`)
    }
    if (status === 'running') {
      return options.t(`adapterStore.${prefix}Running`)
    }
    if (status === 'succeeded') {
      return options.t(`adapterStore.${prefix}Succeeded`)
    }
    if (status === 'failed') {
      return activeTask.value?.error || options.t(`adapterStore.${prefix}Failed`)
    }
    return ''
  })
  const actionLocked = computed(() => actionPending.value || taskIsRunning.value)

  async function reload() {
    loading.value = true
    errorMessage.value = ''
    try {
      await loadSelection({ preserveSelection: true })
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        options.t('core.adapterSelectionLoadFailed'),
      )
    } finally {
      loading.value = false
    }
  }

  async function openPopup() {
    popupVisible.value = true
    manualExpanded.value = false
    popupErrorMessage.value = ''
    await loadPopupSelection()
  }

  async function loadPopupSelection() {
    popupLoading.value = true
    popupErrorMessage.value = ''
    try {
      await loadSelection({ preserveSelection: true })
    } catch (error) {
      popupErrorMessage.value = getErrorMessage(
        error,
        options.t('core.adapterSelectionLoadFailed'),
      )
    } finally {
      popupLoading.value = false
    }
  }

  function schedulePopupReload() {
    if (searchTimer !== null) {
      window.clearTimeout(searchTimer)
    }
    searchTimer = window.setTimeout(() => {
      currentPage.value = 1
      void loadPopupSelection()
    }, 220)
  }

  function selectCandidate(item: AdapterSelectionItem) {
    selectedCandidateKey.value = candidateSelectionKey(item)
    popupErrorMessage.value = ''
  }

  async function applySelectedCandidate() {
    const item = selectedCandidate.value
    if (!item || actionPending.value) {
      return
    }
    if (item.is_enabled) {
      return
    }
    if (item.is_installed) {
      await enableCandidate(item)
      return
    }
    await installCandidate(item)
  }

  async function enableCandidate(item: AdapterSelectionItem) {
    actionPending.value = true
    popupErrorMessage.value = ''
    try {
      await enableAdapterSelection({ module_name: item.module_name })
      options.restartStore.markPending({
        id: `adapter-enable:${item.module_name}`,
        scope: 'core',
        summary: options.t('restart.pendingAdapterConfig'),
        undo: {
          kind: 'adapter-config',
          modules: enabledAdapters.value.map(entry => entry.module_name),
        },
      })
      options.noticeStore.show(
        options.t('core.adapterSelectionEnabled'),
        'success',
      )
      await loadSelection({ preserveSelection: true })
    } catch (error) {
      popupErrorMessage.value = getErrorMessage(
        error,
        options.t('core.adapterSelectionEnableFailed'),
      )
      options.noticeStore.show(popupErrorMessage.value, 'error')
    } finally {
      actionPending.value = false
    }
  }

  async function disableAdapter(item: AdapterSelectionItem) {
    actionPending.value = true
    errorMessage.value = ''
    const previousModules = enabledAdapters.value.map(entry => entry.module_name)
    try {
      await disableAdapterSelection({ module_name: item.module_name })
      options.restartStore.markPending({
        id: `adapter-disable:${item.module_name}`,
        scope: 'core',
        summary: options.t('restart.pendingAdapterConfig'),
        undo: {
          kind: 'adapter-config',
          modules: previousModules,
        },
      })
      options.noticeStore.show(
        options.t('core.adapterSelectionDisabled'),
        'success',
      )
      await loadSelection({ preserveSelection: true })
    } catch (error) {
      const message = getErrorMessage(
        error,
        options.t('core.adapterSelectionDisableFailed'),
      )
      errorMessage.value = message
      options.noticeStore.show(message, 'error')
    } finally {
      actionPending.value = false
    }
  }

  async function installCandidate(item: AdapterSelectionItem) {
    if (!item.source_id || !item.adapter_id || !item.package_name) {
      popupErrorMessage.value = options.t('core.adapterSelectionInstallUnavailable')
      return
    }
    if (actionLocked.value) {
      return
    }
    actionPending.value = true
    popupErrorMessage.value = ''
    activeItem.value = item
    taskMode.value = 'install'
    try {
      const response = await installAdapterStoreItem({
        source_id: item.source_id,
        adapter_id: item.adapter_id,
        package_name: item.package_name,
        module_name: item.module_name,
      })
      activeTask.value = response.data
      taskDialogVisible.value = true
      startTaskPolling(response.data.task_id)
    } catch (error) {
      popupErrorMessage.value = getErrorMessage(
        error,
        options.t('adapterStore.installFailed'),
      )
      options.noticeStore.show(popupErrorMessage.value, 'error')
    } finally {
      actionPending.value = false
    }
  }

  async function installManual() {
    if (!canSubmitManualInstall.value || actionLocked.value) {
      return
    }
    actionPending.value = true
    popupErrorMessage.value = ''
    const requirement = manualRequirement.value.trim()
    try {
      const response = await installManualAdapter({
        requirement,
        module_name: manualModuleName.value.trim() || undefined,
      })
      activeItem.value = null
      taskMode.value = 'manual-install'
      activeTask.value = response.data
      taskDialogVisible.value = true
      startTaskPolling(response.data.task_id, { requirement })
    } catch (error) {
      popupErrorMessage.value = getErrorMessage(
        error,
        options.t('adapterStore.installFailed'),
      )
      options.noticeStore.show(popupErrorMessage.value, 'error')
    } finally {
      actionPending.value = false
    }
  }

  async function updateAdapter(item: AdapterSelectionItem) {
    if (!item.source_id || !item.adapter_id || !item.package_name) {
      return
    }
    if (actionLocked.value) {
      return
    }
    actionPending.value = true
    activeItem.value = item
    taskMode.value = 'update'
    try {
      const response = await updateAdapterStoreItem({
        source_id: item.source_id,
        adapter_id: item.adapter_id,
        package_name: item.package_name,
        module_name: item.module_name,
      })
      activeTask.value = response.data
      taskDialogVisible.value = true
      startTaskPolling(response.data.task_id)
    } catch (error) {
      options.noticeStore.show(
        getErrorMessage(error, options.t('adapterStore.updateFailed')),
        'error',
      )
    } finally {
      actionPending.value = false
    }
  }

  async function uninstallAdapter(item: AdapterSelectionItem) {
    const packageName = item.installed_package || item.package_name
    if (!packageName) {
      return
    }
    if (actionLocked.value) {
      return
    }
    actionPending.value = true
    activeItem.value = item
    taskMode.value = 'uninstall'
    try {
      const response = await uninstallAdapterStoreItem({
        package_name: packageName,
        module_name: item.module_name,
      })
      activeTask.value = response.data
      taskDialogVisible.value = true
      startTaskPolling(response.data.task_id)
    } catch (error) {
      options.noticeStore.show(
        getErrorMessage(error, options.t('adapterStore.uninstallFailed')),
        'error',
      )
    } finally {
      actionPending.value = false
    }
  }

  function closePopup() {
    popupVisible.value = false
    manualExpanded.value = false
    popupErrorMessage.value = ''
  }

  function stopTaskPolling() {
    if (taskPollTimer !== null) {
      window.clearInterval(taskPollTimer)
      taskPollTimer = null
    }
  }

  function startTaskPolling(
    taskId: string,
    manualContext?: { requirement: string },
  ) {
    stopTaskPolling()
    taskPollTimer = window.setInterval(async () => {
      try {
        const response = await getAdapterStoreTask(taskId)
        activeTask.value = response.data
        if (response.data.status === 'succeeded' || response.data.status === 'failed') {
          stopTaskPolling()
          if (response.data.status === 'succeeded') {
            markRestartPending(response.data, manualContext)
            options.noticeStore.show(
              options.t(`adapterStore.${taskMessagePrefix()}Succeeded`),
              'success',
            )
            await loadSelection({ preserveSelection: true })
          } else {
            options.noticeStore.show(
              response.data.error
              || options.t(`adapterStore.${taskMessagePrefix()}Failed`),
              'error',
            )
          }
        }
      } catch (error) {
        stopTaskPolling()
        options.noticeStore.show(
          getErrorMessage(error, options.t(`adapterStore.${taskMessagePrefix()}Failed`)),
          'error',
        )
      }
    }, 1000)
  }

  function taskMessagePrefix() {
    return taskMode.value === 'manual-install' ? 'install' : taskMode.value
  }

  function markRestartPending(
    task: AdapterStoreTask,
    manualContext?: { requirement: string },
  ) {
    const resultModule = typeof task.result.module_name === 'string'
      ? task.result.module_name
      : activeItem.value?.module_name || manualModuleName.value.trim()
    const resultRequirement = typeof task.result.requirement === 'string'
      ? task.result.requirement
      : activeItem.value?.installed_package
        || activeItem.value?.package_name
        || manualContext?.requirement
        || ''
    const label = activeItem.value?.display_name || resultModule || resultRequirement

    if (taskMode.value === 'install' || taskMode.value === 'manual-install') {
      options.restartStore.markPending({
        id: `adapter-store-install:${resultModule || resultRequirement}`,
        scope: 'core',
        summary: options.t('restart.pendingAdapterInstall', { name: label }),
        undo: {
          kind: 'adapter-install',
          packageName: resultRequirement,
          moduleName: resultModule,
        },
      })
      return
    }
    if (taskMode.value === 'update') {
      options.restartStore.markPending({
        id: `adapter-store-update:${resultModule || resultRequirement}`,
        scope: 'core',
        summary: options.t('restart.pendingAdapterUpdate', { name: label }),
      })
      return
    }
    options.restartStore.markPending({
      id: `adapter-store-uninstall:${resultModule || resultRequirement}`,
      scope: 'core',
      summary: options.t('restart.pendingAdapterUninstall', { name: label }),
    })
  }

  async function loadSelection(options?: { preserveSelection?: boolean }) {
    const previousSelectionKey = selectedCandidateKey.value
    const response = await getAdapterSelection({
      search: search.value || undefined,
      unenabled_only: unenabledOnly.value || undefined,
      page: currentPage.value,
      per_page: pageSize,
    })
    selection.value = response.data
    if (options?.preserveSelection && previousSelectionKey) {
      const matched = response.data.candidates.find(item =>
        candidateSelectionKey(item) === previousSelectionKey,
      )
      if (matched) {
        selectedCandidateKey.value = candidateSelectionKey(matched)
        return
      }
    }
    selectedCandidateKey.value = response.data.candidates[0]
      ? candidateSelectionKey(response.data.candidates[0])
      : ''
  }

  function retryActiveTask() {
    if (taskMode.value === 'manual-install') {
      void installManual()
      return
    }
    const item = activeItem.value
    if (!item || actionLocked.value) {
      return
    }
    if (taskMode.value === 'update') {
      void updateAdapter(item)
      return
    }
    if (taskMode.value === 'uninstall') {
      void uninstallAdapter(item)
      return
    }
    void installCandidate(item)
  }

  onBeforeUnmount(() => {
    stopTaskPolling()
    if (searchTimer !== null) {
      window.clearTimeout(searchTimer)
      searchTimer = null
    }
  })

  return {
    actionPending,
    actionLocked,
    activeTask,
    canRetryTask,
    canSubmitManualInstall,
    candidates,
    closePopup,
    currentPage,
    disableAdapter,
    enabledAdapters,
    errorMessage,
    installManual,
    loadPopupSelection,
    loading,
    manualExpanded,
    manualModuleName,
    manualRequirement,
    openPopup,
    popupErrorMessage,
    popupLoading,
    popupVisible,
    reload,
    schedulePopupReload,
    search,
    selectCandidate,
    selectedCandidate,
    selectedCandidateKey,
    summary,
    taskDialogVisible,
    taskFailed,
    taskIsRunning,
    taskStatusLabel,
    taskStatusTone,
    unenabledOnly,
    uninstallAdapter,
    updateAdapter,
    applySelectedCandidate,
    retryActiveTask,
  }
}
