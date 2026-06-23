import client from "@/api/client"

export interface AccountItem {
  user_id: string
  username: string
  is_disabled: boolean
  last_login_at: string | null
  password_changed_at: string | null
}

export const accountsService = {
  list() {
    return client.get<AccountItem[]>("/auth/accounts").then((r) => r.data)
  },

  create(payload: { username: string; password: string }) {
    return client.post<{ detail: string }>("/auth/accounts", payload).then((r) => r.data)
  },

  delete(userId: string) {
    return client.delete<{ detail: string }>(`/auth/accounts/${userId}`).then((r) => r.data)
  },

  disable(userId: string) {
    return client.post<{ detail: string }>(`/auth/accounts/${userId}/disable`).then((r) => r.data)
  },

  resetPassword(userId: string, password: string) {
    return client
      .post<{ detail: string }>(`/auth/accounts/${userId}/reset-password`, { password })
      .then((r) => r.data)
  },

  changePassword(current_password: string, new_password: string) {
    return client
      .post<{ detail: string }>("/auth/change-password", { current_password, new_password })
      .then((r) => r.data)
  },

  revokeOtherSessions() {
    return client.post<{ detail: string }>("/auth/sessions/revoke-others").then((r) => r.data)
  },
}
