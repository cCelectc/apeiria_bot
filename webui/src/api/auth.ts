import client from './client'

export interface WebUIPrincipal {
  user_id: string
  username: string
  role: string
  capabilities: string[]
}

export interface WebUIAccountItem {
  user_id: string
  username: string
  role: string
  is_disabled: boolean
  last_login_at: string | null
  password_changed_at: string | null
}

export interface SecurityAuditEventItem {
  event_type: string
  occurred_at: string
  actor_username: string | null
  target_username: string | null
  detail: string | null
}

export function login(payload: {
  username: string
  password: string
}) {
  return client.post<{ principal: WebUIPrincipal }>('/auth/login', payload)
}

export function logout() {
  return client.post<{ status: string, detail?: string | null }>('/auth/logout')
}

export function register(payload: {
  registration_code: string
  username: string
  password: string
}) {
  return client.post<{ status: string, detail?: string | null }>('/auth/register', payload)
}

export function getCurrentUser() {
  return client.get<WebUIPrincipal>('/auth/me')
}

export function getCurrentAccount() {
  return client.get<WebUIAccountItem>('/auth/me/account')
}

export function changePassword(payload: {
  current_password: string
  new_password: string
}) {
  return client.post<{
    status: string
    detail?: string | null
    principal: WebUIPrincipal
  }>('/auth/password', payload)
}

export function getSecurityAuditEvents() {
  return client.get<SecurityAuditEventItem[]>('/auth/audit-events')
}

export function revokeOtherSessions() {
  return client.post<{
    status: string
    detail?: string | null
    principal: WebUIPrincipal
  }>('/auth/sessions/revoke-others')
}
