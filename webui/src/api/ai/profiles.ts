import client from '@/api/client'
import type {
  AIModelBindingItem,
  AIModelProfileItem,
} from './types'

export function getAIModelProfiles() {
  return client.get<AIModelProfileItem[]>('/ai/model-profiles')
}

export function upsertAIModelProfile(payload: {
  profile_id?: string | null
  name: string
  model_id: string
  task_class: string
  priority: number
  enabled: boolean
}) {
  return client.put<AIModelProfileItem | null>('/ai/model-profiles', payload)
}

export function getAIModelBindings() {
  return client.get<AIModelBindingItem[]>('/ai/model-bindings')
}
