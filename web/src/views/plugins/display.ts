import type { PluginItem, PluginUpdateCheckItem } from '@/api/plugins'
import {
  displayChoiceTitle,
  type PluginSettingChoice,
} from '@/views/plugins/settingsEditor'

export type PluginTranslate = (
  key: string,
  params?: Record<string, unknown>,
) => string

const SOURCE_COLORS: Record<string, string> = {
  framework: 'error',
  custom: 'success',
  builtin: 'secondary',
  external: 'warning',
}

export function sourceColor (source: string) {
  return SOURCE_COLORS[source] || 'default'
}

export function labelFromMap (source: string, map: Record<string, string>) {
  return map[source] || source
}

export function sourceLabel (source: string, t: PluginTranslate) {
  return labelFromMap(source, {
    framework: t('plugins.framework'),
    custom: t('plugins.custom'),
    builtin: t('plugins.builtin'),
    external: t('plugins.external'),
  })
}

export function pluginMetaSummary (item: PluginItem) {
  const author = item.author?.trim()
  const version = item.version?.trim()
  if (author && version) {
    return `${author} · ${version}`
  }
  if (author) {
    return author
  }
  if (version) {
    return `v${version}`
  }
  return ''
}

export function pluginUpdateCheck (
  checks: Record<string, PluginUpdateCheckItem>,
  item: PluginItem,
) {
  return checks[item.module_name] || null
}

export function hasPluginUpdate (
  checks: Record<string, PluginUpdateCheckItem>,
  item: PluginItem,
) {
  return !!pluginUpdateCheck(checks, item)?.has_update
}

export function updateButtonTooltip (
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

export function pluginToggleHint (item: PluginItem, t: PluginTranslate) {
  if (item.is_pending_uninstall) {
    return t('plugins.pendingUninstallHint')
  }
  if (item.is_protected && item.protected_reason) {
    return item.protected_reason
  }
  return ''
}

export function pluginProjectUrl (item: PluginItem) {
  const candidate = item.homepage || ''
  if (candidate.startsWith('http://') || candidate.startsWith('https://')) {
    return candidate
  }
  return ''
}

export function settingsSourceLabel (source: string, t: PluginTranslate) {
  return labelFromMap(source, {
    static_scan: t('plugins.settingsSourceStaticScan'),
    plugin_metadata: t('plugins.settingsSourceMetadata'),
    none: t('plugins.settingsSourceNone'),
    manual: t('plugins.settingsSourceManual'),
    built_in: t('plugins.settingsSourceBuiltIn'),
  })
}

export function settingsValueSourceLabel (source: string, t: PluginTranslate) {
  return labelFromMap(source, {
    default: t('plugins.settingsValueSourceDefault'),
    plugin_section: t('plugins.settingsValueSourcePlugin'),
    legacy_global: t('plugins.settingsValueSourceLegacy'),
    env: t('plugins.settingsValueSourceEnv'),
  })
}

export function formatFieldChoices (choices: PluginSettingChoice[]) {
  const normalized = choices
    .map(choice => displayChoiceTitle(choice))
    .filter(Boolean)

  if (normalized.length <= 4) {
    return normalized.join(' / ')
  }

  return `${normalized.slice(0, 4).join(' / ')} +${normalized.length - 4}`
}
