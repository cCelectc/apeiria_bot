import type { OrphanPluginConfigItem, PluginItem } from '@/api/plugins'
import type { RestartPendingEntry } from '@/stores/restart'
import type { PluginTranslate } from '@/views/plugins/display'
import { computed, ref, type Ref } from 'vue'
import { getErrorMessage } from '@/api/client'
import {
  cleanupOrphanPluginConfigs,
  getOrphanPluginConfigs,
  getPluginTogglePreview,
  uninstallPlugin,
  updatePlugin,
} from '@/api/plugins'
import {
  toggleConfirmTitle as buildToggleConfirmTitle,
  uninstallConfirmSummary as buildUninstallConfirmSummary,
  canUninstallPlugin as canUninstallPluginForRole,
  canUpdatePlugin as canUpdatePluginForRole,
} from '@/views/plugins/actions'

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

interface RestartStoreLike {
  markPending: (entry: Omit<RestartPendingEntry, 'updated_at'>) => void
}

export function usePluginActions (options: {
  errorMessage: Ref<string>
  getPluginLabel: (moduleName: string) => string
  loadPluginManagement: () => Promise<void>
  noticeStore: NoticeStoreLike
  pendingModule: Ref<string>
  plugins: Ref<PluginItem[]>
  restartStore: RestartStoreLike
  settingsDialogVisible: Ref<boolean>
  settingsPlugin: Ref<PluginItem | null>
  t: PluginTranslate
}) {
  const toggleConfirmVisible = ref(false)
  const toggleConfirmLoading = ref(false)
  const toggleConfirmItem = ref<PluginItem | null>(null)
  const toggleConfirmNextValue = ref(false)
  const toggleConfirmSummaryText = ref('')
  const toggleConfirmDependencies = ref<string[]>([])
  const uninstallingModule = ref('')
  const uninstallConfirmVisible = ref(false)
  const uninstallConfirmItem = ref<PluginItem | null>(null)
  const uninstallRemoveConfig = ref(false)
  const orphanConfigDialogVisible = ref(false)
  const orphanConfigLoading = ref(false)
  const orphanConfigCleaning = ref(false)
  const orphanConfigItems = ref<OrphanPluginConfigItem[]>([])

  const toggleConfirmTitle = computed(() =>
    buildToggleConfirmTitle(toggleConfirmNextValue.value, options.t),
  )
  const toggleConfirmSummary = computed(() => toggleConfirmSummaryText.value)
  const uninstallConfirmSummary = computed(() =>
    buildUninstallConfirmSummary(uninstallConfirmItem.value, options.t),
  )

  function closeToggleConfirm () {
    toggleConfirmVisible.value = false
    toggleConfirmLoading.value = false
    toggleConfirmItem.value = null
    toggleConfirmNextValue.value = false
    toggleConfirmSummaryText.value = ''
    toggleConfirmDependencies.value = []
  }

  function closeUninstallConfirm () {
    uninstallConfirmVisible.value = false
    uninstallConfirmItem.value = null
    uninstallRemoveConfig.value = false
  }

  async function openOrphanConfigDialog () {
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

  function openToggleConfirm (
    item: PluginItem,
    enabled: boolean,
    summary: string,
    dependencies: string[],
  ) {
    toggleConfirmItem.value = item
    toggleConfirmNextValue.value = enabled
    toggleConfirmSummaryText.value = summary
    toggleConfirmDependencies.value = dependencies
    toggleConfirmVisible.value = true
  }

  function canUninstallPlugin (item: PluginItem, role?: string | null) {
    return canUninstallPluginForRole(role, item)
  }

  function canUpdatePlugin (item: PluginItem, role?: string | null) {
    return canUpdatePluginForRole(role, item)
  }

  async function uninstallPluginItem (item: PluginItem) {
    uninstallConfirmItem.value = item
    uninstallRemoveConfig.value = false
    uninstallConfirmVisible.value = true
  }

  async function confirmUninstallPlugin () {
    if (!uninstallConfirmItem.value) {
      return
    }
    const item = uninstallConfirmItem.value
    uninstallingModule.value = item.module_name
    try {
      await uninstallPlugin(item.module_name, {
        remove_config: uninstallRemoveConfig.value,
      })
      options.noticeStore.show(options.t('plugins.settingsUninstallSucceeded'), 'success')
      if (options.settingsPlugin.value?.module_name === item.module_name) {
        options.settingsDialogVisible.value = false
        options.settingsPlugin.value = null
      }
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

  async function confirmCleanupOrphanConfigs () {
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
    } catch (error) {
      options.noticeStore.show(
        getErrorMessage(error, options.t('plugins.orphanConfigCleanupFailed')),
        'error',
      )
    } finally {
      orphanConfigCleaning.value = false
    }
  }

  async function togglePlugin (item: PluginItem, nextValue: boolean | null) {
    if (item.is_pending_uninstall) {
      options.noticeStore.show(options.t('plugins.pendingUninstallHint'), 'warning')
      return
    }
    if (item.is_protected) {
      options.noticeStore.show(
        item.protected_reason || options.t('plugins.cannotDisable'),
        'warning',
      )
      return
    }
    const enabled = Boolean(nextValue)
    item.is_global_enabled = !enabled
    options.pendingModule.value = item.module_name
    options.errorMessage.value = ''
    try {
      const preview = (await getPluginTogglePreview(item.module_name, enabled)).data
      if (!preview.allowed) {
        const message = preview.blocked_reason || options.t('plugins.cannotDisable')
        options.errorMessage.value = message
        options.noticeStore.show(message, 'warning')
        return
      }
      const dependencies = enabled ? preview.requires_enable : preview.requires_disable
      if (dependencies.length > 0) {
        openToggleConfirm(item, enabled, preview.summary, dependencies)
        return
      }
      await executeToggle(item, enabled, false)
    } catch (error) {
      options.errorMessage.value = getErrorMessage(error, options.t('plugins.updateFailed'))
      options.noticeStore.show(options.errorMessage.value, 'error')
    } finally {
      options.pendingModule.value = ''
    }
  }

  async function executeToggle (
    item: PluginItem,
    enabled: boolean,
    cascade: boolean,
  ) {
    const previous = item.is_global_enabled
    item.is_global_enabled = enabled
    options.pendingModule.value = item.module_name
    options.errorMessage.value = ''
    try {
      const response = await updatePlugin(item.module_name, enabled, cascade)
      const affectedModules = response.data.affected_modules
      options.restartStore.markPending({
        id: `plugin:toggle:${item.module_name}`,
        scope: 'plugins',
        summary: options.t('restart.pendingPluginToggle', {
          name: item.name || item.module_name,
        }),
        undo: {
          kind: 'plugin-toggle',
          moduleName: item.module_name,
          enabled: previous,
        },
      })
      await options.loadPluginManagement()
      if (options.settingsPlugin.value) {
        options.settingsPlugin.value = options.plugins.value.find(
          candidate => candidate.module_name === options.settingsPlugin.value?.module_name,
        ) || options.settingsPlugin.value
      }
      const linkedModules = affectedModules.filter(moduleName => moduleName !== item.module_name)
      const affectedSummary = linkedModules.length > 0
        ? ` (${linkedModules.map(moduleName => options.getPluginLabel(moduleName)).join(', ')})`
        : ''
      options.noticeStore.show(
        options.t('plugins.toggled', {
          name: item.name || item.module_name,
          action: enabled
            ? options.t('plugins.enabledAction')
            : options.t('plugins.disabledAction'),
        }) + affectedSummary,
        'success',
      )
    } catch (error) {
      item.is_global_enabled = previous
      options.errorMessage.value = getErrorMessage(error, options.t('plugins.updateFailed'))
      options.noticeStore.show(options.errorMessage.value, 'error')
    } finally {
      options.pendingModule.value = ''
    }
  }

  async function confirmToggleAction () {
    if (!toggleConfirmItem.value) {
      return
    }
    toggleConfirmLoading.value = true
    try {
      await executeToggle(toggleConfirmItem.value, toggleConfirmNextValue.value, true)
      closeToggleConfirm()
    } finally {
      toggleConfirmLoading.value = false
    }
  }

  return {
    canUninstallPlugin,
    canUpdatePlugin,
    closeToggleConfirm,
    closeUninstallConfirm,
    confirmCleanupOrphanConfigs,
    confirmToggleAction,
    confirmUninstallPlugin,
    openOrphanConfigDialog,
    orphanConfigCleaning,
    orphanConfigDialogVisible,
    orphanConfigItems,
    orphanConfigLoading,
    toggleConfirmDependencies,
    toggleConfirmItem,
    toggleConfirmLoading,
    toggleConfirmNextValue,
    toggleConfirmSummary,
    toggleConfirmTitle,
    toggleConfirmVisible,
    togglePlugin,
    uninstallConfirmItem,
    uninstallConfirmSummary,
    uninstallConfirmVisible,
    uninstallPluginItem,
    uninstallRemoveConfig,
    uninstallingModule,
  }
}
