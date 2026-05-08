import type {
  AIKnowledgeChunkItem,
  AIKnowledgeDocumentItem,
  AIKnowledgeRebuildDiagnosticsItem,
  AIKnowledgeRetrievalResultItem,
  AIKnowledgeStateItem,
  AIKnowledgeUploadResultItem,
} from './types'

import client from '../client'

export function getAIKnowledgeState () {
  return client.get<AIKnowledgeStateItem>('/ai/knowledge/state')
}

export function updateAIKnowledgeState (ragEnabled: boolean) {
  return client.patch<AIKnowledgeStateItem>('/ai/knowledge/state', {
    rag_enabled: ragEnabled,
  })
}

export function uploadAIKnowledgeDocument (payload: {
  source_file_name: string
  content: string
}) {
  return client.post<AIKnowledgeUploadResultItem>('/ai/knowledge/documents', payload)
}

export function getAIKnowledgeDocuments () {
  return client.get<AIKnowledgeDocumentItem[]>('/ai/knowledge/documents')
}

export function getAIKnowledgeChunks (documentId: string) {
  return client.get<AIKnowledgeChunkItem[]>(
    `/ai/knowledge/documents/${documentId}/chunks`,
  )
}

export function rebuildAIKnowledgeDocument (documentId: string) {
  return client.post<AIKnowledgeRebuildDiagnosticsItem>(
    `/ai/knowledge/documents/${documentId}/rebuild`,
  )
}

export function deleteAIKnowledgeDocument (documentId: string) {
  return client.delete<{ deleted: boolean }>(
    `/ai/knowledge/documents/${documentId}`,
  )
}

export function previewAIKnowledgeRetrieval (payload: {
  query_text: string
  limit: number
}) {
  return client.post<AIKnowledgeRetrievalResultItem>(
    '/ai/knowledge/retrieval/preview',
    payload,
  )
}
