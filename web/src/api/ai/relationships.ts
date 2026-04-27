import type { AIRelationshipEventItem, AIRelationshipStateItem } from './types'

import client from '../client'

export function getAIRelationshipStates (params?: {
  limit?: number
}) {
  return client.get<AIRelationshipStateItem[]>('/ai/relationships/list', {
    params,
  })
}

export function getAIRelationshipState (params: {
  platform: string
  user_id: string
  group_id?: string
}) {
  return client.get<AIRelationshipStateItem>('/ai/relationships', { params })
}

export function updateAIRelationshipScore (payload: {
  platform: string
  user_id: string
  group_id?: string | null
  score: number
}) {
  return client.patch<AIRelationshipStateItem>('/ai/relationships', payload)
}

export function getAIRelationshipEvents (params: {
  platform: string
  user_id: string
  group_id?: string
  limit?: number
}) {
  return client.get<AIRelationshipEventItem[]>('/ai/relationships/events', {
    params,
  })
}
