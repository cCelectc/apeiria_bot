import axios from "axios"

const client = axios.create({
  baseURL: "/api",
  withCredentials: true,
  timeout: 30_000,
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const url: string = error.config?.url ?? ""

    if (status === 401 || status === 403) {
      const isAuthRoute = url.includes("/auth/login") || url.includes("/auth/password")
      if (!isAuthRoute && window.location.pathname !== "/login") {
        window.location.href = "/login"
      }
    }

    return Promise.reject(error)
  },
)

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data
    if (data && typeof data === "object") {
      const apiError = data as { message?: string }
      if (typeof apiError.message === "string" && apiError.message.trim()) {
        return apiError.message
      }
    }
    if (typeof data === "string" && data.trim()) {
      return data
    }
    if (error.message) {
      return error.message
    }
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}

export default client
