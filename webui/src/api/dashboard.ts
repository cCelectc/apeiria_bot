import client from './client'

export interface DashboardStatus {
  status: string
  uptime: number
  plugins_count: number
  disabled_plugins_count: number
  groups_count: number
  disabled_groups_count: number
  access_rules_count: number
  adapters: string[]
}

export interface DashboardEventItem {
  timestamp: string
  level: string
  source: string
  message: string
}

export interface WebUIBuildStatus {
  is_built: boolean
  is_stale: boolean
  can_build: boolean
  build_tool: string | null
  detail: string | null
}

export interface WebUIBuildRunResult extends WebUIBuildStatus {
  logs: string
}

export interface WebUIBuildStreamEvent {
  event: 'chunk' | 'done' | 'error'
  chunk?: string
  detail?: string | null
  status?: WebUIBuildStatus
}

export function getStatus() {
  return client.get<DashboardStatus>('/dashboard/status')
}

export function getDashboardEvents() {
  return client.get<{ items: DashboardEventItem[] }>('/dashboard/events')
}

export function getWebUIBuildStatus() {
  return client.get<WebUIBuildStatus>('/dashboard/webui-build')
}

export function rebuildWebUI() {
  return client.post<WebUIBuildRunResult>('/dashboard/webui-build')
}

function clearSessionAndRedirect() {
  window.location.href = '/login'
}

export async function streamRebuildWebUI(
  onEvent: (event: WebUIBuildStreamEvent) => void | Promise<void>,
) {
  const response = await fetch('/api/dashboard/webui-build/stream', {
    credentials: 'same-origin',
    method: 'POST',
  })

  if (response.status === 401 || response.status === 403) {
    clearSessionAndRedirect()
    throw new Error('Unauthorized')
  }

  if (!response.ok) {
    const body = await response.text()
    let detail = body
    try {
      const payload = JSON.parse(body) as { detail?: string }
      detail = payload.detail || body
    } catch {
      // Keep plain-text error bodies as-is.
    }
    throw new Error(detail || 'Failed to rebuild WebUI')
  }

  if (!response.body) {
    throw new Error('Build log stream unavailable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    let lineBreakIndex = buffer.indexOf('\n')
    while (lineBreakIndex >= 0) {
      const line = buffer.slice(0, lineBreakIndex).trim()
      buffer = buffer.slice(lineBreakIndex + 1)
      if (line) {
        await onEvent(JSON.parse(line) as WebUIBuildStreamEvent)
      }
      lineBreakIndex = buffer.indexOf('\n')
    }

    if (done) {
      const line = buffer.trim()
      if (line) {
        await onEvent(JSON.parse(line) as WebUIBuildStreamEvent)
      }
      break
    }
  }
}

export function restartBot() {
  return client.post<{ status: string, detail?: string | null }>('/dashboard/restart')
}
