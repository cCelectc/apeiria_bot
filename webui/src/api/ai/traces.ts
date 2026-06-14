import client from '@/api/client'
import type {
  AIModelUsageEventItem,
  AIModelUsageSummaryItem,
  AITurnTraceItem,
} from './types'

export function getAITurnTraces(params?: {
  limit?: number
  trace_id?: string
  session_id?: string
  runtime_mode?: string
  terminal_status?: string
  commit_status?: string
}) {
  return client.get<AITurnTraceItem[]>('/ai/traces', { params })
}

export function getAIUsageEvents(params?: {
  limit?: number
  trace_id?: string
  session_id?: string
  source_id?: string
  model_name?: string
  response_source?: string
  operation?: string
  created_from?: string
  created_to?: string
}) {
  return client.get<AIModelUsageEventItem[]>('/ai/usage-events', { params })
}

export function getAIUsageSummary(params?: {
  group_by?: 'trace' | 'session' | 'source' | 'model' | 'response_source' | 'operation'
  trace_id?: string
  session_id?: string
  source_id?: string
  model_name?: string
  response_source?: string
  operation?: string
  created_from?: string
  created_to?: string
}) {
  return client.get<AIModelUsageSummaryItem[]>('/ai/usage-summary', { params })
}
