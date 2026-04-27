import client from './client'

export interface LogItem {
  timestamp: string
  level: string
  source: string
  message: string
  raw: string
  extra: Record<string, unknown>
}

export interface LogHistoryResponse {
  items: LogItem[]
  total: number
  before: number
  next_before: number | null
  has_more: boolean
}

export interface LogSourcesResponse {
  items: string[]
}

export interface LogHistoryQuery {
  before?: number
  limit?: number
  level?: string
  source?: string
  search?: string
  start?: string
  end?: string
  include_access?: boolean
}

export function getLogHistory (params?: LogHistoryQuery, signal?: AbortSignal) {
  return client.get<LogHistoryResponse>('/logs/history', { params, signal })
}

export function getLogSources (signal?: AbortSignal) {
  return client.get<LogSourcesResponse>('/logs/sources', { signal })
}
