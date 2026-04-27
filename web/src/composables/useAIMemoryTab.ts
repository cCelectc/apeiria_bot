import type { AIMemoryItem, AIRecentTargetItem } from '@/api/ai/types'
import { computed, reactive, ref } from 'vue'
import {
  bulkDeleteAIMemories,
  bulkToggleAIMemoryIgnored,
  createAIMemory,
  deleteAIMemory,
  getAIMemories,
  getAIRecentTargets,
  toggleAIMemoryIgnored,
  updateAIMemory,
} from '@/api/ai/memories'
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
    anchor_type: 'scene',
    anchor_id: '',
    memory_layer: '',
    memory_kind: '',
    query: '',
    limit: 20,
  })
  const memoryDraft = reactive({
    memory_layer: 'long_term',
    memory_kind: 'fact',
    content: '',
  })
  const memoryEditDraft = reactive({
    content: '',
    salience: 0.6,
    confidence: 0.8,
  })

  const selectedMemoryIds = ref<Set<string>>(new Set())
  const bulkActionLoading = ref(false)
  const togglingIgnoredId = ref('')

  const selectedMemoryCount = computed(() => selectedMemoryIds.value.size)
  const allMemoriesSelected = computed(() => (
    memories.value.length > 0
    && selectedMemoryIds.value.size === memories.value.length
  ))

  const canLoadMemories = computed(() => memoryForm.anchor_id.trim().length > 0)
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
      memories.value = memoryForm.memory_kind
        ? response.data.filter(item => item.memory_kind === memoryForm.memory_kind)
        : response.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryLoadFailed')), 'error')
    } finally {
      loadingMemories.value = false
    }
  }

  async function selectRecentTarget (item: AIRecentTargetItem) {
    selectedRecentTargetId.value = `${item.anchor_type}:${item.anchor_id}`
    memoryForm.anchor_type = item.anchor_type
    memoryForm.anchor_id = item.anchor_id
    await loadMemories()
  }

  async function saveMemory () {
    if (!canSaveMemory.value) {
      return
    }
    savingMemory.value = true
    try {
      await createAIMemory({
        memory_layer: memoryDraft.memory_layer,
        memory_kind: memoryDraft.memory_kind,
        anchor_type: memoryForm.anchor_type,
        anchor_id: memoryForm.anchor_id.trim(),
        content: memoryDraft.content.trim(),
      })
      memoryForm.memory_layer = memoryDraft.memory_layer
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
    if (!item.is_editable) {
      return
    }
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

  function toggleMemorySelection (memoryId: string) {
    const next = new Set(selectedMemoryIds.value)
    if (next.has(memoryId)) {
      next.delete(memoryId)
    } else {
      next.add(memoryId)
    }
    selectedMemoryIds.value = next
  }

  function toggleSelectAll () {
    selectedMemoryIds.value = allMemoriesSelected.value
      ? new Set()
      : new Set(memories.value.map(item => item.memory_id))
  }

  function clearSelection () {
    selectedMemoryIds.value = new Set()
  }

  async function toggleIgnored (memoryId: string) {
    togglingIgnoredId.value = memoryId
    try {
      const response = await toggleAIMemoryIgnored(memoryId)
      if (response.data) {
        memories.value = memories.value.map(item => (
          item.memory_id === response.data?.memory_id ? response.data : item
        ))
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryToggleIgnoredFailed')), 'error')
    } finally {
      togglingIgnoredId.value = ''
    }
  }

  async function bulkDelete () {
    const ids = [...selectedMemoryIds.value]
    if (ids.length === 0) {
      return
    }
    bulkActionLoading.value = true
    try {
      const response = await bulkDeleteAIMemories(ids)
      const deletedSet = new Set(ids)
      memories.value = memories.value.filter(item => !deletedSet.has(item.memory_id))
      selectedMemoryIds.value = new Set()
      noticeStore.show(`${t('ai.memoryBulkDeleted')}: ${response.data.affected}`, 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryBulkDeleteFailed')), 'error')
    } finally {
      bulkActionLoading.value = false
    }
  }

  async function bulkSetIgnored (ignored: boolean) {
    const ids = [...selectedMemoryIds.value]
    if (ids.length === 0) {
      return
    }
    bulkActionLoading.value = true
    try {
      await bulkToggleAIMemoryIgnored(ids, ignored)
      memories.value = memories.value.map(item => (
        ids.includes(item.memory_id) ? { ...item, is_ignored: ignored } : item
      ))
      selectedMemoryIds.value = new Set()
      noticeStore.show(t('ai.memoryBulkIgnoreUpdated'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryBulkIgnoreFailed')), 'error')
    } finally {
      bulkActionLoading.value = false
    }
  }

  return {
    allMemoriesSelected,
    bulkActionLoading,
    bulkDelete,
    bulkSetIgnored,
    cancelEditMemory,
    canLoadMemories,
    canSaveMemory,
    canSaveEditedMemory,
    clearSelection,
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
    selectedMemoryCount,
    selectedMemoryIds,
    selectRecentTarget,
    selectedRecentTargetId,
    startEditMemory,
    toggleIgnored,
    toggleMemorySelection,
    toggleSelectAll,
    togglingIgnoredId,
  }
}
