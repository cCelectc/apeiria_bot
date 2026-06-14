import client from '@/api/client'
import type {
  AISkillItem,
  AIToolExecutionItem,
  AIToolItem,
} from './types'

export function getAISkills() {
  return client.get<AISkillItem[]>('/ai/skills')
}

export function reloadAISkills() {
  return client.post<AISkillItem[]>('/ai/skills/reload')
}

export function getAITools() {
  return client.get<AIToolItem[]>('/ai/tools')
}

export function getAIRecentToolExecutions(params?: { limit?: number }) {
  return client.get<AIToolExecutionItem[]>('/ai/tools/executions/recent', { params })
}
