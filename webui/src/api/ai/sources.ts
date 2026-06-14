import client from '@/api/client'
import type {
  AIBootstrapResponse,
  AIRuntimeStatusResponse,
  AIRuntimeSettingsResponse,
  AIRuntimeSettingsUpdateRequest,
  AISourceApiKeyAction,
  AISourceItem,
  AISourcePresetItem,
} from './types'

export { AIBootstrapResponse, AIRuntimeStatusResponse, AIRuntimeSettingsResponse, AIRuntimeSettingsUpdateRequest }

export function getAIBootstrap() {
  return client.get<AIBootstrapResponse>('/ai/bootstrap')
}

export function getAIRuntimeStatus() {
  return client.get<AIRuntimeStatusResponse>('/ai/runtime-status')
}

export function getAIRuntimeSettings() {
  return client.get<AIRuntimeSettingsResponse>('/ai/runtime-settings')
}

export function updateAIRuntimeSettings(payload: AIRuntimeSettingsUpdateRequest) {
  return client.patch<AIRuntimeSettingsResponse>('/ai/runtime-settings', payload)
}

export function getAISources() {
  return client.get<AISourceItem[]>('/ai/sources')
}

export function getAISourcePresets() {
  return client.get<AISourcePresetItem[]>('/ai/source-presets')
}

export function createAISource(payload: {
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
  api_key_action?: AISourceApiKeyAction | null
  api_keys?: string[]
}) {
  return client.post<AISourceItem>('/ai/sources', payload)
}

export function updateAISource(payload: {
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
  api_key_action?: AISourceApiKeyAction | null
  api_keys?: string[]
}) {
  return client.put<AISourceItem | null>('/ai/sources', payload)
}

export function deleteAISource(sourceId: string) {
  return client.delete<boolean>('/ai/sources', {
    params: { source_id: sourceId },
  })
}
