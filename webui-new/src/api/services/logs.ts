import client from "@/api/client"

export interface LogItem {
  timestamp: string
  level: string
  source: string
  message: string
}

export const logsService = {
  history(params: {
    page?: number
    page_size?: number
    level?: string
    source?: string
    search?: string
    start_time?: string
    end_time?: string
  }) {
    return client.get<{ items: LogItem[]; total: number }>("/logs/history", { params }).then((r) => r.data)
  },

  sources() {
    return client.get<string[]>("/logs/sources").then((r) => r.data)
  },
}
