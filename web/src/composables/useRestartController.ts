import type { RestartUndoAction } from '@/stores/restart'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import { updateCoreSettings, updateCoreSettingsRaw, updatePluginConfig } from '@/api/core'
import { getStatus, restartBot } from '@/api/dashboard'
import {
  revertPluginStoreInstall,
  updatePlugin,
  updatePluginSettings,
  updatePluginSettingsRaw,
} from '@/api/plugins'
import { useNoticeStore } from '@/stores/notice'
import { useRestartStore } from '@/stores/restart'

export function useRestartController () {
  const restarting = ref(false)
  const reverting = ref(false)
  const noticeStore = useNoticeStore()
  const restartStore = useRestartStore()
  const { t } = useI18n()

  async function restartAndReload () {
    if (restarting.value) {
      return false
    }
    restarting.value = true
    try {
      const res = await restartBot()
      noticeStore.show(res.data.detail || t('dashboard.restartScheduled'), 'success')
      await waitForRestartTransition()
      restartStore.clearPending()
      window.location.reload()
      return true
    } catch (error) {
      const message = getErrorMessage(error, t('dashboard.restartFailed'))
      noticeStore.show(message, 'error')
      return false
    } finally {
      restarting.value = false
    }
  }

  async function revertPendingChanges () {
    if (reverting.value || restartStore.entries.length === 0) {
      return false
    }
    reverting.value = true
    try {
      const entries = [...restartStore.entries]
      for (const entry of entries) {
        if (!entry.undo) {
          continue
        }
        await revertEntry(entry.undo)
      }
      restartStore.clearPending()
      noticeStore.show(t('restart.reverted'), 'success')
      window.location.reload()
      return true
    } catch (error) {
      const message = getErrorMessage(error, t('restart.revertFailed'))
      noticeStore.show(message, 'error')
      return false
    } finally {
      reverting.value = false
    }
  }

  return {
    reverting,
    restarting,
    revertPendingChanges,
    restartAndReload,
  }
}

async function revertEntry (undo: RestartUndoAction) {
  switch (undo.kind) {
    case 'core-settings': {
      await updateCoreSettings({ values: undo.values })
      return
    }
    case 'core-raw': {
      await updateCoreSettingsRaw({ text: undo.text })
      return
    }
    case 'plugin-settings': {
      await updatePluginSettings(undo.moduleName, { values: undo.values })
      return
    }
    case 'plugin-raw': {
      await updatePluginSettingsRaw(undo.moduleName, { text: undo.text })
      return
    }
    case 'plugin-config': {
      await updatePluginConfig({ modules: undo.modules, dirs: undo.dirs })
      return
    }
    case 'plugin-toggle': {
      await updatePlugin(undo.moduleName, undo.enabled)
      return
    }
    case 'plugin-install': {
      await revertPluginStoreInstall({
        package_name: undo.packageName,
        module_name: undo.moduleName,
      })
      return
    }
  }
}

async function waitForRestartTransition () {
  await waitForStatus(false, 30, 1000)
  await waitForStatus(true, 60, 1000)
}

async function waitForStatus (expectedOnline: boolean, maxAttempts: number, delayMs: number) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await sleep(delayMs)
    try {
      await getStatus()
      if (expectedOnline) {
        return
      }
    } catch {
      if (!expectedOnline) {
        return
      }
    }
  }

  throw new Error('restart timeout')
}

function sleep (ms: number) {
  return new Promise(resolve => window.setTimeout(resolve, ms))
}
