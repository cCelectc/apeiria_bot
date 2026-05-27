import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const client = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 10_000,
})

client.interceptors.response.use(
  response => response,
  error => {
    const status = error.response?.status
    const requestUrl = typeof error.config?.url === 'string'
      ? error.config.url
      : ''
    const authStore = useAuthStore()
    if (
      status === 401
      && authStore.status !== 'anonymous'
      && !isCredentialRequest(requestUrl)
    ) {
      authStore.handleUnauthorized()
      window.location.href = '/login'
    }
    if (
      status === 403
      && authStore.status !== 'anonymous'
      && requestUrl.includes('/auth/me')
    ) {
      authStore.clearSession('anonymous')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

function joinValidationErrors(detail: unknown) {
  if (!Array.isArray(detail)) {
    return ''
  }
  return detail
    .map(item => {
      if (!item || typeof item !== 'object') {
        return ''
      }
      const entry = item as { loc?: unknown, msg?: unknown }
      const path = Array.isArray(entry.loc) ? entry.loc.join('.') : ''
      const message = typeof entry.msg === 'string' ? entry.msg : ''
      if (!message) {
        return ''
      }
      return path ? `${path}: ${message}` : message
    })
    .filter(Boolean)
    .join('\n')
}

export function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data
    if (typeof data === 'string' && data.trim()) {
      return data
    }
    if (data && typeof data === 'object') {
      const detail = (data as { detail?: unknown }).detail
      if (typeof detail === 'string' && detail.trim()) {
        return detail
      }
      const validationMessage = joinValidationErrors(detail)
      if (validationMessage) {
        return validationMessage
      }
      const message = (data as { message?: unknown }).message
      if (typeof message === 'string' && message.trim()) {
        return message
      }
    }
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}

function isCredentialRequest(requestUrl: string) {
  return requestUrl.includes('/auth/login')
    || requestUrl.includes('/auth/password')
}

export default client
