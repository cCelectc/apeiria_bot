import type { AIMemoryItem } from '@/api'
import { reactive, ref } from 'vue'
import { getAIMemories } from '@/api'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIMemoryTab (t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const loadingMemories = ref(false)
  const memories = ref<AIMemoryItem[]>([])
  const memoryForm = reactive({
    subject_type: 'user',
    subject_id: '',
    query: '',
    limit: 20,
  })

  async function loadMemories () {
    loadingMemories.value = true
    try {
      const response = await getAIMemories(memoryForm)
      memories.value = response.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryLoadFailed')), 'error')
    } finally {
      loadingMemories.value = false
    }
  }

  return {
    loadMemories,
    loadingMemories,
    memories,
    memoryForm,
  }
}
