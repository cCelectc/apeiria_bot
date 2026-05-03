import { computed, ref } from 'vue'
import { getErrorMessage } from '@/api/client'

export function useAIPageLoader (
  loadFailedText: () => string,
  afterLoad?: () => void,
) {
  const loading = ref(false)
  const errorMessage = ref('')

  async function runPageLoad (loader: () => Promise<void>) {
    loading.value = true
    errorMessage.value = ''
    try {
      await loader()
      afterLoad?.()
    } catch (error) {
      errorMessage.value = getErrorMessage(error, loadFailedText())
    } finally {
      loading.value = false
    }
  }

  return {
    errorMessage,
    loading,
    runPageLoad,
  }
}

export function useAISourceCapabilityOptions (
  t: (key: string) => string,
) {
  const sourceCapabilityOptions = computed(() => [
    { icon: 'mdi-message-text-outline', title: t('ai.sourceCapabilityChat'), value: 'chat' as const },
    { icon: 'mdi-microphone-outline', title: t('ai.sourceCapabilityStt'), value: 'stt' as const },
    { icon: 'mdi-volume-high', title: t('ai.sourceCapabilityTts'), value: 'tts' as const },
    { icon: 'mdi-vector-polyline', title: t('ai.sourceCapabilityEmbedding'), value: 'embedding' as const },
    { icon: 'mdi-sort-variant', title: t('ai.sourceCapabilityRerank'), value: 'rerank' as const },
  ])

  return {
    sourceCapabilityOptions,
  }
}

export function usePersonProfilePointCategoryOptions (
  t: (key: string) => string,
) {
  const personProfilePointCategoryOptions = computed(() => [
    { title: t('ai.personProfileCategoryFact'), value: 'fact' },
    { title: t('ai.personProfileCategoryPreference'), value: 'preference' },
    { title: t('ai.personProfileCategoryRelationship'), value: 'relationship' },
    { title: t('ai.personProfileCategoryImpression'), value: 'impression' },
  ])

  return {
    personProfilePointCategoryOptions,
  }
}
