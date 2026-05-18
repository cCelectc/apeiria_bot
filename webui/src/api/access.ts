import client from './client'

export interface AccessRuleItem {
  subject_type: 'user' | 'group' | string
  subject_id: string
  plugin_module: string
  effect: 'allow' | 'deny' | string
  note: string | null
}

export interface AccessRulesResponse {
  items: AccessRuleItem[]
}

export interface AccessRulePayload {
  subject_type: string
  subject_id: string
  plugin_module: string
  effect: string
  note?: string | null
}

export function getAccessRules() {
  return client.get<AccessRuleItem[] | AccessRulesResponse>('/permissions/rules')
}

export function createAccessRule(payload: AccessRulePayload) {
  return client.post<AccessRuleItem>('/permissions/rules', payload)
}

export function deleteAccessRule(payload: {
  subject_type: string
  subject_id: string
  plugin_module: string
}) {
  return client.post<{ status: string }>('/permissions/rules/delete', payload)
}

export function updatePluginAccessMode(moduleName: string, accessMode: string) {
  return client.patch<{ status: string }>(
    `/permissions/plugins/${encodeURIComponent(moduleName)}/access-mode`,
    { access_mode: accessMode },
  )
}

export function normalizeAccessRulesResponse(data: unknown): AccessRuleItem[] {
  if (Array.isArray(data)) {
    return data as AccessRuleItem[]
  }
  if (data && typeof data === 'object' && Array.isArray((data as AccessRulesResponse).items)) {
    return (data as AccessRulesResponse).items
  }
  return []
}
