import type { AIMemoryItem, AIRecentTargetItem } from '@/api'
import { computed, reactive, ref } from 'vue'
import { createAIMemory, deleteAIMemory, getAIMemories, getAIRecentTargets, updateAIMemory } from '@/api'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIMemoryTab (t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const loadingMemories = ref(false)
  const loadingRecentTargets = ref(false)
  const savingMemory = ref(false)
  const savingEditedMemoryId = ref('')
  const deletingMemoryId = ref('')
  const editingMemoryId = ref('')
  const memories = ref<AIMemoryItem[]>([])
  const recentTargets = ref<AIRecentTargetItem[]>([])
  const selectedRecentTargetId = ref('')
  const memoryForm = reactive({
    subject_type: 'user',
    subject_id: '',
    memory_domain: '',
    memory_type: '',
    query: '',
    limit: 20,
  })
  const memoryDraft = reactive({
    memory_domain: 'knowledge',
    memory_type: 'fact',
    content: '',
  })
  const memoryEditDraft = reactive({
    content: '',
    salience: 0.6,
    confidence: 0.8,
  })

  const canLoadMemories = computed(() => memoryForm.subject_id.trim().length > 0)
  const canSaveMemory = computed(() => (
    canLoadMemories.value
    && memoryDraft.content.trim().length > 0
    && !savingMemory.value
  ))
  const canSaveEditedMemory = computed(() => (
    editingMemoryId.value.trim().length > 0
    && memoryEditDraft.content.trim().length > 0
    && !savingEditedMemoryId.value
  ))

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
      memories.value = memoryForm.memory_type
        ? response.data.filter(item => item.memory_type === memoryForm.memory_type)
        : response.data
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

  async function saveMemory () {
    if (!canSaveMemory.value) {
      return
    }
    savingMemory.value = true
    try {
      await createAIMemory({
        memory_domain: memoryDraft.memory_domain,
        memory_type: memoryDraft.memory_type,
        subject_type: memoryForm.subject_type,
        subject_id: memoryForm.subject_id.trim(),
        content: memoryDraft.content.trim(),
      })
      memoryForm.memory_domain = memoryDraft.memory_domain
      memoryDraft.content = ''
      noticeStore.show(t('ai.memorySaved'), 'success')
      await loadMemories()
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memorySaveFailed')), 'error')
    } finally {
      savingMemory.value = false
    }
  }

  async function removeMemory (memoryId: string) {
    deletingMemoryId.value = memoryId
    try {
      await deleteAIMemory(memoryId)
      memories.value = memories.value.filter(item => item.memory_id !== memoryId)
      noticeStore.show(t('ai.memoryDeleted'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryDeleteFailed')), 'error')
    } finally {
      deletingMemoryId.value = ''
    }
  }

  function startEditMemory (item: AIMemoryItem) {
    editingMemoryId.value = item.memory_id
    memoryEditDraft.content = item.content
    memoryEditDraft.salience = item.salience
    memoryEditDraft.confidence = item.confidence
  }

  function cancelEditMemory () {
    editingMemoryId.value = ''
    memoryEditDraft.content = ''
    memoryEditDraft.salience = 0.6
    memoryEditDraft.confidence = 0.8
  }

  async function saveEditedMemory () {
    if (!canSaveEditedMemory.value) {
      return
    }
    savingEditedMemoryId.value = editingMemoryId.value
    try {
      const response = await updateAIMemory({
        memory_id: editingMemoryId.value,
        content: memoryEditDraft.content.trim(),
        salience: memoryEditDraft.salience,
        confidence: memoryEditDraft.confidence,
      })
      if (response.data) {
        memories.value = memories.value.map(item => (
          item.memory_id === response.data?.memory_id ? response.data : item
        ))
      }
      noticeStore.show(t('ai.memoryUpdated'), 'success')
      cancelEditMemory()
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryUpdateFailed')), 'error')
    } finally {
      savingEditedMemoryId.value = ''
    }
  }

  return {
    cancelEditMemory,
    canLoadMemories,
    canSaveMemory,
    canSaveEditedMemory,
    deletingMemoryId,
    editingMemoryId,
    loadMemories,
    loadRecentTargets,
    loadingMemories,
    loadingRecentTargets,
    memoryEditDraft,
    memories,
    memoryDraft,
    memoryForm,
    recentTargets,
    removeMemory,
    saveMemory,
    saveEditedMemory,
    savingEditedMemoryId,
    savingMemory,
    selectRecentTarget,
    selectedRecentTargetId,
    startEditMemory,
  }
}
