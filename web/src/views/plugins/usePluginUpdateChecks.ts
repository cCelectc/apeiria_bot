import type { PluginItem, PluginUpdateCheckItem } from '@/api/plugins'
import type { PluginTranslate } from '@/views/plugins/display'
import { ref } from 'vue'
import { getErrorMessage } from '@/api/client'
import { checkPluginUpdates } from '@/api/plugins'
import {
  updateButtonTooltip as buildUpdateButtonTooltip,
  hasPluginUpdate as hasPluginUpdateForChecks,
} from '@/views/plugins/display'

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

export function usePluginUpdateChecks (
  t: PluginTranslate,
  noticeStore: NoticeStoreLike,
) {
  const updateCheckLoading = ref(false)
  const pluginUpdateChecks = ref<Record<string, PluginUpdateCheckItem>>({})

  async function runPluginUpdateCheck (forceRefresh = false) {
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
      noticeStore.show(getErrorMessage(error, t('plugins.updateCheckFailed')), 'error')
    } finally {
      updateCheckLoading.value = false
    }
  }

  function hasPluginUpdate (item: PluginItem) {
    return hasPluginUpdateForChecks(pluginUpdateChecks.value, item)
  }

  function updateButtonTooltip (item: PluginItem) {
    return buildUpdateButtonTooltip(
      pluginUpdateChecks.value,
      item,
      updateCheckLoading.value,
      t,
    )
  }

  return {
    hasPluginUpdate,
    pluginUpdateChecks,
    runPluginUpdateCheck,
    updateButtonTooltip,
    updateCheckLoading,
  }
}
