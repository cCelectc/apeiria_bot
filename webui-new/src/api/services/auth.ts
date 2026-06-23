import client from "@/api/client"
import type { ApiResponse } from "@/types/api"

export interface AuthPrincipal {
  id: string
  username: string
}

export const authService = {
  async login(username: string, password: string): Promise<AuthPrincipal> {
    const res = await client.post<ApiResponse<AuthPrincipal>>("/auth/login", { username, password })
    return res.data.data
  },

  async logout(): Promise<void> {
    await client.post("/auth/logout")
  },

  async me(): Promise<AuthPrincipal> {
    const res = await client.get<AuthPrincipal | ApiResponse<AuthPrincipal>>("/auth/me")
    const data = res.data
    if (typeof data === "object" && data !== null && "username" in data) {
      return data as AuthPrincipal
    }
    return (data as ApiResponse<AuthPrincipal>).data
  },
}
