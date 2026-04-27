import type { PluginItem } from '@/api/plugins'
import type { PluginTranslate } from '@/views/plugins/display'

export function toggleConfirmTitle (nextValue: boolean, t: PluginTranslate) {
  return nextValue
    ? t('plugins.enableConfirmTitle')
    : t('plugins.disableConfirmTitle')
}

export function uninstallConfirmSummary (
  item: PluginItem | null,
  t: PluginTranslate,
) {
  if (!item) {
    return ''
  }
  const pluginName = item.name || item.module_name
  if (item.installed_package) {
    return t('plugins.settingsUninstallConfirm', {
      name: pluginName,
      package: item.installed_package,
    })
  }
  return t('plugins.settingsUninstallConfirmFallback', {
    name: pluginName,
  })
}

export function canUninstallPlugin (role: string | null | undefined, item: PluginItem) {
  return role === 'owner' && item.can_uninstall
}

export function canUpdatePlugin (role: string | null | undefined, item: PluginItem) {
  return (
    role === 'owner'
    && item.can_package_update
    && !item.is_pending_uninstall
    && !!item.installed_package
  )
}
