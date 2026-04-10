import type {
  AIModelBindingItem,
  AIModelProfileItem,
  AIProviderItem,
} from '@/api'
import { ref } from 'vue'
import {
  getAIModelBindings,
  getAIModelProfiles,
  getAIProviders,
} from '@/api'

export function useAIModelsTab () {
  const providers = ref<AIProviderItem[]>([])
  const modelProfiles = ref<AIModelProfileItem[]>([])
  const modelBindings = ref<AIModelBindingItem[]>([])

  async function loadModelsData () {
    const [providersResponse, profilesResponse, bindingsResponse] = await Promise.all([
      getAIProviders(),
      getAIModelProfiles(),
      getAIModelBindings(),
    ])
    providers.value = providersResponse.data
    modelProfiles.value = profilesResponse.data
    modelBindings.value = bindingsResponse.data
  }

  return {
    loadModelsData,
    modelBindings,
    modelProfiles,
    providers,
  }
}
