import type {
  AIMemoryBulkActionResult,
  AIMemoryCreateRequest,
  AIMemoryItem,
  AIRecentTargetItem,
} from './types'

import client from '../client'

export function getAIMemories (params: {
  anchor_type: string
  anchor_id: string
  memory_layer?: string
  memory_kind?: string
  query?: string
  limit?: number
}) {
  return client.get<AIMemoryItem[]>('/ai/memories', { params })
}

export function createAIMemory (payload: AIMemoryCreateRequest) {
  return client.post<AIMemoryItem>('/ai/memories', payload)
}

export function updateAIMemory (payload: {
  memory_id: string
  content: string
  salience: number
  confidence: number
}) {
  return client.patch<AIMemoryItem | null>('/ai/memories', payload)
}

export function deleteAIMemory (memoryId: string) {
  return client.delete<{ deleted: boolean }>('/ai/memories', {
    params: { memory_id: memoryId },
  })
}

export function getAIRecentTargets (params?: {
  limit?: number
}) {
  return client.get<AIRecentTargetItem[]>('/ai/recent-targets', { params })
}

export function toggleAIMemoryIgnored (memoryId: string) {
  return client.patch<AIMemoryItem | null>('/ai/memories/toggle-ignored', {
    memory_id: memoryId,
  })
}

export function bulkDeleteAIMemories (memoryIds: string[]) {
  return client.post<AIMemoryBulkActionResult>('/ai/memories/bulk-delete', {
    memory_ids: memoryIds,
  })
}

export function bulkToggleAIMemoryIgnored (
  memoryIds: string[],
  ignored: boolean,
) {
  return client.post<AIMemoryBulkActionResult>(
    '/ai/memories/bulk-toggle-ignored',
    {
      memory_ids: memoryIds,
      ignored,
    },
  )
}
