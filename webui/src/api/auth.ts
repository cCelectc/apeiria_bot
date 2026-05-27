import client from './client'

export interface WebUIPrincipal {
  user_id: string
  username: string
}

export interface WebUIAccountItem {
  user_id: string
  username: string
  is_disabled: boolean
  last_login_at: string | null
  password_changed_at: string | null
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

export function getCurrentUser() {
  return client.get<WebUIPrincipal>('/auth/me')
}

export function getAccounts() {
  return client.get<WebUIAccountItem[]>('/auth/accounts')
}

export function createAccount(payload: {
  username: string
  password: string
  actor_password: string
}) {
  return client.post<WebUIAccountItem>('/auth/accounts', payload)
}

export function updateAccountDisabled(userId: string, payload: {
  is_disabled: boolean
  actor_password: string
}) {
  return client.patch<WebUIAccountItem>(`/auth/accounts/${userId}`, payload)
}

export function deleteAccount(userId: string, payload: {
  actor_password: string
}) {
  return client.delete<{ status: string, detail?: string | null }>(`/auth/accounts/${userId}`, {
    data: payload,
  })
}

export function resetAccountPassword(userId: string, payload: {
  new_password: string
  actor_password: string
}) {
  return client.post<WebUIAccountItem>(`/auth/accounts/${userId}/reset-password`, payload)
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

export function revokeOtherSessions() {
  return client.post<{
    status: string
    detail?: string | null
    principal: WebUIPrincipal
  }>('/auth/sessions/revoke-others')
}
