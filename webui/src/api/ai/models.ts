import client from '@/api/client'
import type {
  AIModelCatalogItem,
  AISourceModelItem,
  AISourceModelTestResult,
} from './types'

export function getAISourceModels(sourceId: string) {
  return client.get<AISourceModelItem[]>('/ai/sources/models', {
    params: { source_id: sourceId },
  })
}

export function fetchAISourceModels(payload: {
  source_id?: string | null
  preset_type?: string | null
  api_base?: string | null
  api_key?: string | null
  extra_config?: Record<string, unknown>
}) {
  return client.post<AIModelCatalogItem[]>('/ai/sources/models/fetch', payload)
}

export function testAISourceModel(payload: {
  source_id?: string | null
  preset_type?: string | null
  api_base?: string | null
  api_key?: string | null
  extra_config?: Record<string, unknown>
  model_identifier: string
}) {
  return client.post<AISourceModelTestResult>('/ai/sources/models/test', payload)
}

export function createAISourceModel(payload: {
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
  extra_params?: Record<string, unknown>
  capability_metadata?: Record<string, unknown>
  default_options?: Record<string, unknown>
  capability_provenance?: Record<string, unknown>
}) {
  return client.post<AISourceModelItem>('/ai/sources/models', payload)
}

export function updateAISourceModel(payload: {
  model_id: string
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
  extra_params?: Record<string, unknown>
  capability_metadata?: Record<string, unknown>
  default_options?: Record<string, unknown>
  capability_provenance?: Record<string, unknown>
}) {
  return client.put<AISourceModelItem | null>('/ai/sources/models', payload)
}

export function deleteAISourceModel(modelId: string, sourceId?: string) {
  return client.delete<boolean>('/ai/sources/models', {
    params: {
      model_id: modelId,
      source_id: sourceId,
    },
  })
}
