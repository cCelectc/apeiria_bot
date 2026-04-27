import type {
  AIPersonaBindingItem,
  AIPersonaItem,
  AIPersonMemoryPointItem,
  AIPersonProfileItem,
} from './types'

import client from '../client'

export function getAIPersonas () {
  return client.get<AIPersonaItem[]>('/ai/personas')
}

export function getAIPersonaBindings () {
  return client.get<AIPersonaBindingItem[]>('/ai/persona-bindings')
}

export function upsertAIPersona (payload: {
  persona_id?: string | null
  name: string
  description: string
  system_prompt: string
  style_prompt: string
  enabled: boolean
}) {
  return client.put<AIPersonaItem | null>('/ai/personas', payload)
}

export function getAIPersonProfiles (params?: {
  limit?: number
}) {
  return client.get<AIPersonProfileItem[]>('/ai/person-profiles', { params })
}

export function getAIPersonProfile (params: {
  platform: string
  user_id: string
}) {
  return client.get<AIPersonProfileItem | null>(
    '/ai/person-profiles/detail',
    { params },
  )
}

export function updateAIPersonProfile (payload: {
  person_id: string
  person_name?: string | null
  nickname?: string | null
  memory_points?: AIPersonMemoryPointItem[] | null
}) {
  return client.patch<AIPersonProfileItem | null>(
    '/ai/person-profiles',
    payload,
  )
}

export function deleteAIPersonProfile (personId: string) {
  return client.delete<boolean>('/ai/person-profiles', {
    params: { person_id: personId },
  })
}
