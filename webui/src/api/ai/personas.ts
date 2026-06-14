import client from '@/api/client'
import type {
  AIPersonaBindingItem,
  AIPersonaItem,
} from './types'

export function getAIPersonas() {
  return client.get<AIPersonaItem[]>('/ai/personas')
}

export function upsertAIPersona(payload: {
  persona_id?: string | null
  name: string
  description: string
  system_prompt: string
  style_prompt: string
  enabled: boolean
}) {
  return client.put<AIPersonaItem | null>('/ai/personas', payload)
}

export function getAIPersonaBindings() {
  return client.get<AIPersonaBindingItem[]>('/ai/persona-bindings')
}
