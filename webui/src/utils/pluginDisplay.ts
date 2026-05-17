import type { PluginItem, PluginStoreTask, PluginUpdateCheckItem } from '@/api/plugins'

export type PluginTranslate = (
  key: string,
  params?: Record<string, unknown>,
) => string

export function pluginSourceLabel(source: string, t: PluginTranslate) {
  const map: Record<string, string> = {
    framework: t('plugins.framework'),
    custom: t('plugins.custom'),
    builtin: t('plugins.builtin'),
    external: t('plugins.external'),
  }
  return map[source] || source
}

export function pluginSourceTone(source: string) {
  const map: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
    framework: 'warning',
    custom: 'success',
    builtin: 'info',
    external: 'default',
  }
  return map[source] || 'default'
}

export function pluginMetaSummary(item: PluginItem) {
  const author = item.author?.trim()
  const version = item.version?.trim()
  if (author && version) {
    return `${author} / ${version}`
  }
  if (author) {
    return author
  }
  if (version) {
    return `v${version}`
  }
  return ''
}

export function pluginUpdateCheck(
  checks: Record<string, PluginUpdateCheckItem>,
  item: PluginItem,
) {
  return checks[item.module_name] || null
}

export function hasPluginUpdate(
  checks: Record<string, PluginUpdateCheckItem>,
  item: PluginItem,
) {
  return Boolean(pluginUpdateCheck(checks, item)?.has_update)
}

export function updateButtonTooltip(
  checks: Record<string, PluginUpdateCheckItem>,
  item: PluginItem,
  updateCheckLoading: boolean,
  t: PluginTranslate,
) {
  if (updateCheckLoading) {
    return t('plugins.checkingUpdates')
  }
  const result = pluginUpdateCheck(checks, item)
  if (!result) {
    return t('plugins.updateUnavailable')
  }
  if (result.has_update) {
    return t('plugins.updateAvailableVersion', {
      current: result.current_version || '?',
      latest: result.latest_version || '?',
    })
  }
  if (result.checked) {
    return t('plugins.updateLatestVersion', {
      version: result.current_version || result.latest_version || '?',
    })
  }
  if (result.error?.trim()) {
    return result.error.trim()
  }
  return t('plugins.updateUnavailable')
}

export function pluginProjectUrl(item: PluginItem) {
  const candidate = item.homepage || ''
  if (candidate.startsWith('http://') || candidate.startsWith('https://')) {
    return candidate
  }
  return ''
}

export function pluginToggleHint(item: PluginItem, t: PluginTranslate) {
  if (item.is_pending_uninstall) {
    return t('plugins.pendingUninstallHint')
  }
  if (item.is_protected && item.protected_reason) {
    return item.protected_reason
  }
  return ''
}

export function settingsSourceLabel(source: string, t: PluginTranslate) {
  const map: Record<string, string> = {
    static_scan: t('plugins.settingsSourceStaticScan'),
    plugin_metadata: t('plugins.settingsSourceMetadata'),
    none: t('plugins.settingsSourceNone'),
    manual: t('plugins.settingsSourceManual'),
    built_in: t('plugins.settingsSourceBuiltIn'),
  }
  return map[source] || source
}

export function settingsValueSourceLabel(source: string, t: PluginTranslate) {
  const map: Record<string, string> = {
    default: t('plugins.settingsValueSourceDefault'),
    plugin_section: t('plugins.settingsValueSourcePlugin'),
    env: t('plugins.settingsValueSourceEnv'),
  }
  return map[source] || source
}

export type ManualInstallSourceType = 'pypi' | 'git' | 'local'

export function manualInstallSourceOptions(t: PluginTranslate) {
  return [
    { value: 'pypi', label: t('plugins.manualInstallSourcePypi') },
    { value: 'git', label: t('plugins.manualInstallSourceGit') },
    { value: 'local', label: t('plugins.manualInstallSourceLocal') },
  ] satisfies Array<{ value: ManualInstallSourceType, label: string }>
}

export function manualInstallRequirementLabel(
  sourceType: ManualInstallSourceType,
  t: PluginTranslate,
) {
  if (sourceType === 'git') {
    return t('plugins.manualInstallGitLabel')
  }
  if (sourceType === 'local') {
    return t('plugins.manualInstallLocalLabel')
  }
  return t('plugins.manualInstallPackageLabel')
}

export function manualInstallRequirementHint(
  sourceType: ManualInstallSourceType,
  t: PluginTranslate,
) {
  if (sourceType === 'git') {
    return t('plugins.manualInstallGitHint')
  }
  if (sourceType === 'local') {
    return t('plugins.manualInstallLocalHint')
  }
  return t('plugins.manualInstallPackageHint')
}

export function canSubmitManualInstall(requirement: string) {
  return requirement.trim().length > 0
}

export function summarizeTaskError(message: string | null | undefined) {
  const normalized = message?.trim()
  if (!normalized) {
    return ''
  }
  return normalized.split('\n')[0]?.trim() || normalized
}

export function manualInstallTaskStatusLabel(
  task: PluginStoreTask | null,
  t: PluginTranslate,
) {
  const status = task?.status || ''
  if (status === 'pending' || status === 'queued') {
    return t('plugins.manualInstallPending')
  }
  if (status === 'running') {
    return t('plugins.manualInstallRunning')
  }
  if (status === 'succeeded') {
    return t('plugins.manualInstallSucceeded')
  }
  if (status === 'failed') {
    return summarizeTaskError(task?.error) || t('plugins.manualInstallFailed')
  }
  return ''
}

export function packageUpdateTaskStatusLabel(
  task: PluginStoreTask | null,
  t: PluginTranslate,
) {
  const status = task?.status || ''
  if (status === 'pending' || status === 'queued') {
    return t('plugins.packageUpdatePending')
  }
  if (status === 'running') {
    return t('plugins.packageUpdateRunning')
  }
  if (status === 'succeeded') {
    return t('plugins.packageUpdateSucceeded')
  }
  if (status === 'failed') {
    return summarizeTaskError(task?.error) || t('plugins.packageUpdateFailed')
  }
  return ''
}

export function uninstallConfirmSummary(item: PluginItem | null, t: PluginTranslate) {
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

export function canUninstallPlugin(role: string | null | undefined, item: PluginItem) {
  return role === 'owner' && item.can_uninstall
}

export function canUpdatePlugin(role: string | null | undefined, item: PluginItem) {
  return (
    role === 'owner'
    && item.can_package_update
    && !item.is_pending_uninstall
    && Boolean(item.installed_package)
  )
}
