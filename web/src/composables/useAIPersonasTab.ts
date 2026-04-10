import type { AIPersonaBindingItem, AIPersonaItem } from '@/api'
import { ref } from 'vue'
import { getAIPersonaBindings, getAIPersonas } from '@/api'

export function useAIPersonasTab () {
  const personas = ref<AIPersonaItem[]>([])
  const personaBindings = ref<AIPersonaBindingItem[]>([])

  async function loadPersonasData () {
    const [personasResponse, personaBindingsResponse] = await Promise.all([
      getAIPersonas(),
      getAIPersonaBindings(),
    ])
    personas.value = personasResponse.data
    personaBindings.value = personaBindingsResponse.data
  }

  return {
    loadPersonasData,
    personaBindings,
    personas,
  }
}
