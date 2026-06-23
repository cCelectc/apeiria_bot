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

export interface AuthStatusResponse {
  has_accounts: boolean
}

export function login(payload: {
  username: string
  password: string
}) {
  return client.post<WebUIPrincipal>('/auth/login', payload)
}

export function logout() {
  return client.post<{ detail: string | null }>('/auth/logout')
}

export function getCurrentUser() {
  return client.get<WebUIPrincipal>('/auth/me')
}

export function changePassword(payload: {
  current_password: string
  new_password: string
}) {
  return client.post<WebUIPrincipal>('/auth/change-password', payload)
}

export function getAuthStatus() {
  return client.get<AuthStatusResponse>('/auth/status')
}

export function setupAccount(payload: {
  username: string
  password: string
}) {
  return client.post<WebUIPrincipal>('/auth/setup', payload)
}

export function getAccounts() {
  return client.get<WebUIAccountItem[]>('/auth/accounts')
}

export function createAccount(payload: {
  username: string
  password: string
}) {
  return client.post<WebUIAccountItem>('/auth/accounts', payload)
}

export function deleteAccount(userId: string) {
  return client.delete<{ detail: string | null }>(`/auth/accounts/${userId}`)
}

export function resetAccountPassword(
  userId: string,
  payload: { password: string },
) {
  return client.post<WebUIAccountItem>(
    `/auth/accounts/${userId}/reset-password`,
    payload,
  )
}

export function updateAccountDisabled(
  userId: string,
  payload: { is_disabled: boolean },
) {
  return client.patch<WebUIAccountItem>(`/auth/accounts/${userId}`, payload)
}

export function revokeOtherSessions() {
  return client.post<{ detail: string | null }>('/auth/sessions/revoke-others')
}
