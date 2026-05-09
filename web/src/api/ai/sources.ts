import type { AISourceItem, AISourcePresetItem } from './types'

import client from '../client'

export function getAISourcePresets () {
  return client.get<AISourcePresetItem[]>('/ai/source-presets')
}

export function getAISources () {
  return client.get<AISourceItem[]>('/ai/sources')
}

export function createAISource (payload: {
  name: string
  capability_type: string
  preset_type: string
  api_base?: string | null
  enabled: boolean
  timeout_seconds?: number | null
  custom_headers?: Record<string, string>
  extra_config?: Record<string, unknown>
  adapter_kind?: string | null
  capability_metadata?: Record<string, unknown>
  default_options?: Record<string, unknown>
  capability_provenance?: Record<string, unknown>
}) {
  return client.post<AISourceItem>('/ai/sources', payload)
}

export function updateAISource (payload: {
  source_id: string
  name: string
  capability_type: string
  preset_type: string
  api_base?: string | null
  enabled: boolean
  timeout_seconds?: number | null
  custom_headers?: Record<string, string>
  extra_config?: Record<string, unknown>
  adapter_kind?: string | null
  capability_metadata?: Record<string, unknown>
  default_options?: Record<string, unknown>
  capability_provenance?: Record<string, unknown>
}) {
  return client.put<AISourceItem | null>('/ai/sources', payload)
}

export function deleteAISource (sourceId: string) {
  return client.delete<boolean>('/ai/sources', {
    params: { source_id: sourceId },
  })
}
