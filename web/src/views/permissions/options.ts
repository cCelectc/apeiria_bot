export type Perspective = 'plugins' | 'users' | 'rules'

export type PermissionTranslate = (
  key: string,
  params?: Record<string, unknown>,
) => string

export const levelOptions = [0, 1, 2, 3, 4, 5, 6]

export function perspectiveItems (
  counts: {
    plugins: number
    rules: number
    users: number
  },
  t: PermissionTranslate,
): Array<{ value: Perspective, title: string, meta: string }> {
  return [
    { value: 'plugins', title: t('permissions.pluginsTab'), meta: String(counts.plugins) },
    { value: 'users', title: t('permissions.usersTab'), meta: String(counts.users) },
    { value: 'rules', title: t('permissions.rulesTab'), meta: String(counts.rules) },
  ]
}

export function ruleHeaders (t: PermissionTranslate) {
  return [
    { title: t('permissions.subjectType'), key: 'subject_type' },
    { title: t('permissions.subjectId'), key: 'subject_id' },
    { title: t('permissions.pluginModule'), key: 'plugin_module' },
    { title: t('permissions.effect'), key: 'effect' },
    { title: t('permissions.note'), key: 'note' },
    { title: '', key: 'actions', sortable: false },
  ]
}

export function subjectTypeOptions (t: PermissionTranslate) {
  return [
    { title: t('permissions.user'), value: 'user' },
    { title: t('permissions.group'), value: 'group' },
  ]
}

export function effectOptions (t: PermissionTranslate) {
  return [
    { title: t('permissions.allow'), value: 'allow' },
    { title: t('permissions.deny'), value: 'deny' },
  ]
}

export function accessModeOptions (t: PermissionTranslate) {
  return [
    { title: t('permissions.accessModeDefaultAllow'), value: 'default_allow' },
    { title: t('permissions.accessModeDefaultDeny'), value: 'default_deny' },
  ]
}

export function ruleEffectOptions (t: PermissionTranslate) {
  return [
    { title: t('permissions.effectAll'), value: 'all' },
    { title: t('permissions.allow'), value: 'allow' },
    { title: t('permissions.deny'), value: 'deny' },
  ]
}
