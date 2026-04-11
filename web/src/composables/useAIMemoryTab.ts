import type { AIMemoryItem, AIRecentTargetItem } from '@/api'
import { computed, reactive, ref } from 'vue'
import { getAIMemories, getAIRecentTargets } from '@/api'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIMemoryTab (t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const loadingMemories = ref(false)
  const loadingRecentTargets = ref(false)
  const memories = ref<AIMemoryItem[]>([])
  const recentTargets = ref<AIRecentTargetItem[]>([])
  const selectedRecentTargetId = ref('')
  const memoryForm = reactive({
    subject_type: 'user',
    subject_id: '',
    query: '',
    limit: 20,
  })

  const canLoadMemories = computed(() => memoryForm.subject_id.trim().length > 0)

  async function loadRecentTargets () {
    loadingRecentTargets.value = true
    try {
      const response = await getAIRecentTargets({ limit: 12 })
      if (!Array.isArray(response.data)) {
        throw new TypeError(t('ai.memoryTargetLoadFailed'))
      }
      recentTargets.value = response.data
    } catch (error) {
      recentTargets.value = []
      noticeStore.show(getErrorMessage(error, t('ai.memoryTargetLoadFailed')), 'error')
    } finally {
      loadingRecentTargets.value = false
    }
  }

  async function loadMemories () {
    if (!canLoadMemories.value) {
      memories.value = []
      return
    }
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

  async function selectRecentTarget (item: AIRecentTargetItem) {
    selectedRecentTargetId.value = `${item.subject_type}:${item.subject_id}`
    memoryForm.subject_type = item.subject_type
    memoryForm.subject_id = item.subject_id
    await loadMemories()
  }

  return {
    canLoadMemories,
    loadMemories,
    loadRecentTargets,
    loadingMemories,
    loadingRecentTargets,
    memories,
    memoryForm,
    recentTargets,
    selectRecentTarget,
    selectedRecentTargetId,
  }
}
