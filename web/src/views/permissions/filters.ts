import type { AccessRuleItem, UserLevelItem } from '@/api/access'
import type { PluginItem } from '@/api/plugins'

export interface UserPermissionEntry {
  user_id: string
  groups: number
  rules: number
}

export function manageablePlugins (plugins: PluginItem[]) {
  return plugins.filter(item => item.kind !== 'core' && !item.is_protected)
}

export function pluginModuleOptions (plugins: PluginItem[]) {
  return plugins.map(item => ({
    title: item.name && item.name !== item.module_name
      ? `${item.name} (${item.module_name})`
      : item.module_name,
    value: item.module_name,
  }))
}

export function visiblePlugins (plugins: PluginItem[], search: string) {
  const keyword = search.trim().toLowerCase()
  return plugins.filter(item => {
    if (!keyword) {
      return true
    }
    return `${item.name || ''} ${item.module_name}`.toLowerCase().includes(keyword)
  })
}

export function filteredRules (
  rules: AccessRuleItem[],
  options: {
    effect: 'all' | 'allow' | 'deny'
    search: string
  },
) {
  const keyword = options.search.trim().toLowerCase()
  return rules.filter(item => {
    const matchKeyword = !keyword || [
      item.subject_type,
      item.subject_id,
      item.plugin_module,
      item.effect,
      item.note || '',
    ].some(value => value.toLowerCase().includes(keyword))
    const matchEffect = options.effect === 'all' || item.effect === options.effect
    return matchKeyword && matchEffect
  })
}

export function userEntries (
  users: UserLevelItem[],
  rules: AccessRuleItem[],
): UserPermissionEntry[] {
  const fromLevels = users.map(item => item.user_id)
  const fromRules = rules
    .filter(item => item.subject_type === 'user')
    .map(item => item.subject_id)
  return [...new Set([...fromLevels, ...fromRules])]
    .filter(Boolean)
    .map(userId => ({
      user_id: userId,
      groups: users.filter(item => item.user_id === userId).length,
      rules: rules.filter(
        item => item.subject_type === 'user' && item.subject_id === userId,
      ).length,
    }))
}

export function visibleUserEntries (
  entries: UserPermissionEntry[],
  search: string,
) {
  const keyword = search.trim().toLowerCase()
  return entries.filter(item => {
    if (!keyword) {
      return true
    }
    return item.user_id.toLowerCase().includes(keyword)
  })
}

export function ruleKey (rule: AccessRuleItem): string {
  return `${rule.subject_type}:${rule.subject_id}:${rule.plugin_module}`
}

export function pluginRuleCount (
  rules: AccessRuleItem[],
  moduleName: string,
): number {
  return rules.filter(rule => rule.plugin_module === moduleName).length
}
