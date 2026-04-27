import client from './client'

export interface AccessRuleItem {
  subject_type: string
  subject_id: string
  plugin_module: string
  effect: string
  note: string | null
}

export interface UserLevelItem {
  user_id: string
  group_id: string
  level: number
}

export function getAccessRules () {
  return client.get<AccessRuleItem[]>('/permissions/rules')
}

export function createAccessRule (payload: {
  subject_type: string
  subject_id: string
  plugin_module: string
  effect: string
  note?: string | null
}) {
  return client.post<AccessRuleItem>('/permissions/rules', payload)
}

export function deleteAccessRule (payload: {
  subject_type: string
  subject_id: string
  plugin_module: string
}) {
  return client.post('/permissions/rules/delete', payload)
}

export function updatePluginAccessMode (
  moduleName: string,
  accessMode: string,
) {
  return client.patch(
    '/permissions/plugins/' + encodeURIComponent(moduleName) + '/access-mode',
    { access_mode: accessMode },
  )
}

export function getUsers () {
  return client.get<UserLevelItem[]>('/permissions/users')
}

export function updateUserLevel (userId: string, groupId: string, level: number) {
  return client.patch(`/permissions/users/${userId}`, { level }, {
    params: { group_id: groupId },
  })
}
