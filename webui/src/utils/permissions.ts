import type { AccessRuleItem, UserLevelItem } from '@/api/access'
import type { PluginItem } from '@/api/plugins'

export type PermissionPerspective = 'plugins' | 'users' | 'rules'
export type RuleEffectFilter = '__all__' | 'allow' | 'deny'

export interface UserPermissionEntry {
  user_id: string
  groups: number
  rules: number
}

export const permissionPerspectives: PermissionPerspective[] = [
  'plugins',
  'users',
  'rules',
]

export const subjectTypeValues = ['user', 'group'] as const
export const effectValues = ['allow', 'deny'] as const
export const accessModeValues = ['default_allow', 'default_deny'] as const
export const userLevelValues = [0, 1, 2, 3, 4] as const

export function normalizePermissionPerspective(
  value: unknown,
): PermissionPerspective {
  return typeof value === 'string'
    && permissionPerspectives.includes(value as PermissionPerspective)
    ? value as PermissionPerspective
    : 'plugins'
}

export function manageablePlugins(plugins: PluginItem[]) {
  return plugins.filter(item => item.kind !== 'core' && !item.is_protected)
}

export function pluginLabel(item: PluginItem) {
  return item.name && item.name !== item.module_name
    ? `${item.name} (${item.module_name})`
    : item.module_name
}

export function pluginModuleOptions(plugins: PluginItem[]) {
  return plugins.map(item => ({
    label: pluginLabel(item),
    value: item.module_name,
  }))
}

export function visiblePlugins(plugins: PluginItem[], search: string) {
  const keyword = search.trim().toLowerCase()
  if (!keyword) {
    return plugins
  }
  return plugins.filter(item =>
    [
      item.name,
      item.module_name,
      item.description,
      item.author,
      item.version,
    ].some(value => String(value || '').toLowerCase().includes(keyword)),
  )
}

export function ruleKey(rule: AccessRuleItem): string {
  return `${rule.subject_type}:${rule.subject_id}:${rule.plugin_module}`
}

export function pluginRuleCount(rules: AccessRuleItem[], moduleName: string) {
  return rules.filter(rule => rule.plugin_module === moduleName).length
}

export function filteredRules(
  rules: AccessRuleItem[],
  options: {
    effect: RuleEffectFilter
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
    ].some(value => String(value).toLowerCase().includes(keyword))
    const matchEffect = options.effect === '__all__' || item.effect === options.effect
    return matchKeyword && matchEffect
  })
}

export function userEntries(
  users: UserLevelItem[],
  rules: AccessRuleItem[],
): UserPermissionEntry[] {
  const ids = new Set<string>()
  for (const item of users) {
    if (item.user_id) {
      ids.add(item.user_id)
    }
  }
  for (const item of rules) {
    if (item.subject_type === 'user' && item.subject_id) {
      ids.add(item.subject_id)
    }
  }
  return [...ids]
    .sort((left, right) => left.localeCompare(right))
    .map(userId => ({
      user_id: userId,
      groups: users.filter(item => item.user_id === userId).length,
      rules: rules.filter(
        item => item.subject_type === 'user' && item.subject_id === userId,
      ).length,
    }))
}

export function visibleUserEntries(
  entries: UserPermissionEntry[],
  search: string,
) {
  const keyword = search.trim().toLowerCase()
  if (!keyword) {
    return entries
  }
  return entries.filter(item => item.user_id.toLowerCase().includes(keyword))
}
