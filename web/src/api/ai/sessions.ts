import type {
  AIChatMessageItem,
  AISessionItem,
  AISessionPromptPreviewItem,
} from './types'

import client from '../client'

export function getAIScenes (params?: {
  limit?: number
}) {
  return client.get<AISessionItem[]>('/ai/scenes', { params })
}

export function getAISceneTurns (params: {
  scene_id: string
  limit?: number
}) {
  return client.get<AIChatMessageItem[]>('/ai/scenes/turns', { params })
}

export function getAIScenePromptPreview (params: {
  scene_id: string
  turn_limit?: number
}) {
  return client.get<AISessionPromptPreviewItem | null>(
    '/ai/scenes/prompt-preview',
    { params },
  )
}
