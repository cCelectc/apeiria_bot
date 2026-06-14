import client from '@/api/client'
import type {
  AIChatMessageItem,
  AIManagedSessionDetailItem,
  AIManagedSessionItem,
  AIProfileItem,
  AIRecentTargetItem,
  AIRelationshipEventItem,
  AIRelationshipStateItem,
  AISessionItem,
  AISessionPromptPreviewItem,
} from './types'

export function getAIManagedSessions(params?: { limit?: number }) {
  return client.get<AIManagedSessionItem[]>('/ai/managed-sessions', { params })
}

export function getAIManagedSession(
  sessionId: string,
  params?: { message_limit?: number },
) {
  return client.get<AIManagedSessionDetailItem>(
    `/ai/managed-sessions/${encodeURIComponent(sessionId)}`,
    { params },
  )
}

export function updateAIManagedSessionEnabled(
  sessionId: string,
  aiEnabled: boolean,
) {
  return client.patch<AIManagedSessionDetailItem>(
    `/ai/managed-sessions/${encodeURIComponent(sessionId)}/ai-enabled`,
    { ai_enabled: aiEnabled },
  )
}

export function updateAIManagedSessionPersona(
  sessionId: string,
  personaId: string | null,
) {
  return client.patch<AIManagedSessionDetailItem>(
    `/ai/managed-sessions/${encodeURIComponent(sessionId)}/persona`,
    { persona_id: personaId },
  )
}

export function resetAIManagedSessionContext(sessionId: string) {
  return client.post<AIManagedSessionDetailItem>(
    `/ai/managed-sessions/${encodeURIComponent(sessionId)}/context-reset`,
  )
}

export function getAIRecentTargets(params?: { limit?: number }) {
  return client.get<AIRecentTargetItem[]>('/ai/recent-targets', { params })
}

export function getAIScenes(params?: { limit?: number }) {
  return client.get<AISessionItem[]>('/ai/scenes', { params })
}

export function getAISceneTurns(params: { scene_id: string, limit?: number }) {
  return client.get<AIChatMessageItem[]>('/ai/scenes/turns', { params })
}

export function getAIScenePromptPreview(params: {
  scene_id: string
  turn_limit?: number
}) {
  return client.get<AISessionPromptPreviewItem | null>(
    '/ai/scenes/prompt-preview',
    { params },
  )
}

export function getAIProfiles(params?: { limit?: number }) {
  return client.get<AIProfileItem[]>('/ai/profiles', { params })
}

export function updateAIProfile(payload: {
  profile_id: string
  display_name?: string | null
  preferred_name?: string | null
  name_source?: string | null
  name_visibility?: string | null
  profile_enabled?: boolean | null
}) {
  return client.patch<AIProfileItem | null>('/ai/profiles', payload)
}

export function deleteAIProfile(profileId: string) {
  return client.delete<boolean>('/ai/profiles', {
    params: { profile_id: profileId },
  })
}

export function getAIRelationshipStates(params?: { limit?: number }) {
  return client.get<AIRelationshipStateItem[]>('/ai/relationships/list', {
    params,
  })
}

export function updateAIRelationshipScore(payload: {
  platform: string
  user_id: string
  scene_id?: string | null
  score: number
}) {
  return client.patch<AIRelationshipStateItem>('/ai/relationships', payload)
}

export function getAIRelationshipEvents(params: {
  platform: string
  user_id: string
  limit?: number
}) {
  return client.get<AIRelationshipEventItem[]>('/ai/relationships/events', {
    params,
  })
}
