import type { PluginItem } from '@/api/plugins'

export function buildPluginNameMap (plugins: PluginItem[]) {
  return new Map(
    plugins.map(item => [item.module_name, item.name || item.module_name]),
  )
}

export function getSystemPlugins (plugins: PluginItem[]) {
  return plugins.filter(item => item.kind === 'core')
}

export function getNonSystemPlugins (plugins: PluginItem[]) {
  return plugins.filter(item => item.kind !== 'core')
}

export function getScopedPlugins (
  plugins: PluginItem[],
  scope: 'managed' | 'framework',
) {
  return scope === 'framework'
    ? getSystemPlugins(plugins)
    : getNonSystemPlugins(plugins)
}

export function getVisiblePlugins (
  plugins: PluginItem[],
  options: {
    disabledOnly: boolean
    scope: 'managed' | 'framework'
    search: string
  },
) {
  const scopedPlugins = getScopedPlugins(plugins, options.scope)
  const keyword = options.search.trim().toLowerCase()

  return scopedPlugins.filter(item => {
    if (options.disabledOnly && item.is_global_enabled) {
      return false
    }
    if (!keyword) {
      return true
    }
    return `${item.name || ''} ${item.module_name} ${item.description || ''} ${item.source}`
      .toLowerCase()
      .includes(keyword)
  })
}
