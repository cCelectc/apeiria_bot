import type { AIMemoryItem, AIRecentTargetItem } from '@/api/ai'
import { computed, reactive, ref } from 'vue'
import {
  bulkDeleteAIMemories,
  bulkSetAIMemoryLifecycle,
  createAIMemory,
  deleteAIMemory,
  getAIMemories,
  getAIRecentTargets,
  setAIMemoryLifecycle,
  updateAIMemory,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { ALL_FILTER } from '@/constants'
import { optionalFilter } from '@/composables/useTabHelpers'
import { useNoticeStore } from '@/stores/notice'

export interface MemoryFormState {
  anchor_id: string
  anchor_type: string
  limit: number
  memory_kind: string
  memory_layer: string
  query: string
}

export interface MemoryDraftState {
  content: string
  memory_kind: string
  memory_layer: string
}

export interface MemoryEditDraftState {
  confidence: number
  content: string
  salience: number
}

export function useAIMemoryTab(t: (key: string) => string) {
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
  const selectedMemoryIds = ref<Set<string>>(new Set())
  const bulkActionLoading = ref(false)
  const settingLifecycleId = ref('')
  const memoryForm = reactive<MemoryFormState>({
    anchor_id: '',
    anchor_type: 'scene',
    limit: 20,
    memory_kind: ALL_FILTER,
    memory_layer: ALL_FILTER,
    query: '',
  })
  const memoryDraft = reactive<MemoryDraftState>({
    content: '',
    memory_kind: 'fact',
    memory_layer: 'long_term',
  })
  const memoryEditDraft = reactive<MemoryEditDraftState>({
    confidence: 0.8,
    content: '',
    salience: 0.6,
  })

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
    editingMemoryId.value.length > 0
    && memoryEditDraft.content.trim().length > 0
    && !savingEditedMemoryId.value
  ))

  async function loadRecentTargets() {
    loadingRecentTargets.value = true
    try {
      const response = await getAIRecentTargets({ limit: 20 })
      recentTargets.value = Array.isArray(response.data) ? response.data : []
    } catch (error) {
      recentTargets.value = []
      noticeStore.show(getErrorMessage(error, t('ai.memoryTargetLoadFailed')), 'error')
    } finally {
      loadingRecentTargets.value = false
    }
  }

  async function loadMemories() {
    if (!canLoadMemories.value) {
      memories.value = []
      selectedMemoryIds.value = new Set()
      return
    }
    loadingMemories.value = true
    try {
      const response = await getAIMemories({
        anchor_id: memoryForm.anchor_id.trim(),
        anchor_type: memoryForm.anchor_type,
        limit: memoryForm.limit,
        memory_kind: optionalFilter(memoryForm.memory_kind),
        memory_layer: optionalFilter(memoryForm.memory_layer),
        query: memoryForm.query.trim() || undefined,
      })
      memories.value = response.data
      selectedMemoryIds.value = new Set(
        [...selectedMemoryIds.value].filter(id =>
          response.data.some(item => item.memory_id === id),
        ),
      )
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryLoadFailed')), 'error')
    } finally {
      loadingMemories.value = false
    }
  }

  async function selectRecentTarget(item: AIRecentTargetItem) {
    selectedRecentTargetId.value = `${item.anchor_type}:${item.anchor_id}`
    memoryForm.anchor_id = item.anchor_id
    memoryForm.anchor_type = item.anchor_type
    await loadMemories()
  }

  async function saveMemory() {
    if (!canSaveMemory.value) {
      return
    }
    savingMemory.value = true
    try {
      await createAIMemory({
        anchor_id: memoryForm.anchor_id.trim(),
        anchor_type: memoryForm.anchor_type,
        content: memoryDraft.content.trim(),
        memory_kind: memoryDraft.memory_kind,
        memory_layer: memoryDraft.memory_layer,
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

  async function removeMemory(memoryId: string) {
    deletingMemoryId.value = memoryId
    try {
      await deleteAIMemory(memoryId)
      memories.value = memories.value.filter(item => item.memory_id !== memoryId)
      selectedMemoryIds.value.delete(memoryId)
      selectedMemoryIds.value = new Set(selectedMemoryIds.value)
      noticeStore.show(t('ai.memoryDeleted'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryDeleteFailed')), 'error')
    } finally {
      deletingMemoryId.value = ''
    }
  }

  function startEditMemory(item: AIMemoryItem) {
    if (!item.is_editable) {
      return
    }
    editingMemoryId.value = item.memory_id
    memoryEditDraft.confidence = item.confidence
    memoryEditDraft.content = item.content
    memoryEditDraft.salience = item.salience
  }

  function cancelEditMemory() {
    editingMemoryId.value = ''
    memoryEditDraft.confidence = 0.8
    memoryEditDraft.content = ''
    memoryEditDraft.salience = 0.6
  }

  async function saveEditedMemory() {
    if (!canSaveEditedMemory.value) {
      return
    }
    savingEditedMemoryId.value = editingMemoryId.value
    try {
      const response = await updateAIMemory({
        confidence: clamp01(Number(memoryEditDraft.confidence)),
        content: memoryEditDraft.content.trim(),
        memory_id: editingMemoryId.value,
        salience: clamp01(Number(memoryEditDraft.salience)),
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

  async function setLifecycle(memoryId: string, lifecycleState: string) {
    settingLifecycleId.value = memoryId
    try {
      const response = await setAIMemoryLifecycle(memoryId, lifecycleState)
      if (response.data) {
        memories.value = memories.value.map(item => (
          item.memory_id === response.data?.memory_id ? response.data : item
        ))
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryLifecycleUpdateFailed')), 'error')
    } finally {
      settingLifecycleId.value = ''
    }
  }

  function toggleMemorySelection(memoryId: string) {
    const next = new Set(selectedMemoryIds.value)
    if (next.has(memoryId)) {
      next.delete(memoryId)
    } else {
      next.add(memoryId)
    }
    selectedMemoryIds.value = next
  }

  function toggleSelectAll() {
    selectedMemoryIds.value = allMemoriesSelected.value
      ? new Set()
      : new Set(memories.value.map(item => item.memory_id))
  }

  function clearSelection() {
    selectedMemoryIds.value = new Set()
  }

  async function bulkDelete() {
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

  async function bulkSetLifecycle(lifecycleState: string) {
    const ids = [...selectedMemoryIds.value]
    if (ids.length === 0) {
      return
    }
    bulkActionLoading.value = true
    try {
      await bulkSetAIMemoryLifecycle(ids, lifecycleState)
      const idSet = new Set(ids)
      memories.value = memories.value.map(item => (
        idSet.has(item.memory_id)
          ? { ...item, lifecycle_state: lifecycleState }
          : item
      ))
      selectedMemoryIds.value = new Set()
      noticeStore.show(t('ai.memoryBulkLifecycleUpdated'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.memoryBulkLifecycleFailed')), 'error')
    } finally {
      bulkActionLoading.value = false
    }
  }

  return {
    allMemoriesSelected,
    bulkActionLoading,
    bulkDelete,
    bulkSetLifecycle,
    canLoadMemories,
    canSaveEditedMemory,
    canSaveMemory,
    cancelEditMemory,
    clearSelection,
    deletingMemoryId,
    editingMemoryId,
    loadMemories,
    loadRecentTargets,
    loadingMemories,
    loadingRecentTargets,
    memories,
    memoryDraft,
    memoryEditDraft,
    memoryForm,
    recentTargets,
    removeMemory,
    setLifecycle,
    saveEditedMemory,
    saveMemory,
    savingEditedMemoryId,
    savingMemory,
    selectRecentTarget,
    selectedMemoryCount,
    selectedMemoryIds,
    selectedRecentTargetId,
    startEditMemory,
    toggleMemorySelection,
    toggleSelectAll,
    settingLifecycleId,
  }
}

function clamp01(value: number) {
  if (!Number.isFinite(value)) {
    return 0
  }
  return Math.min(1, Math.max(0, value))
}
