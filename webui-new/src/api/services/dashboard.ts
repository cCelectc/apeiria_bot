import client from "@/api/client"

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

export interface WebUIBuildStreamEvent {
  event: "chunk" | "done" | "error"
  chunk?: string
  detail?: string | null
  status?: WebUIBuildStatus
}

export const dashboardService = {
  getStatus() {
    return client.get<DashboardStatus>("/dashboard/status").then((r) => r.data)
  },

  getEvents() {
    return client.get<{ items: DashboardEventItem[] }>("/dashboard/events").then((r) => r.data)
  },

  getWebUIBuildStatus() {
    return client.get<WebUIBuildStatus>("/dashboard/webui-build").then((r) => r.data)
  },

  rebuildWebUI() {
    return client.post<{ logs: string }>("/dashboard/webui-build").then((r) => r.data)
  },

  async streamRebuildWebUI(onEvent: (event: WebUIBuildStreamEvent) => void) {
    const res = await fetch("/api/dashboard/webui-build/stream", {
      credentials: "same-origin",
      method: "POST",
    })
    if (!res.ok) throw new Error("Build stream failed")
    if (!res.body) throw new Error("Build stream unavailable")

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
      let idx = buffer.indexOf("\n")
      while (idx >= 0) {
        const line = buffer.slice(0, idx).trim()
        buffer = buffer.slice(idx + 1)
        if (line) onEvent(JSON.parse(line))
        idx = buffer.indexOf("\n")
      }
      if (done) {
        if (buffer.trim()) onEvent(JSON.parse(buffer.trim()))
        break
      }
    }
  },

  restartBot() {
    return client.post("/dashboard/restart").then((r) => r.data)
  },
}
