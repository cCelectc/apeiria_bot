import type {
  AIConversationItem,
  AIConversationPromptPreviewItem,
  AIConversationTurnItem,
  AIToolExecutionItem,
} from '@/api'
import { computed, reactive, ref } from 'vue'
import {
  getAIScenePromptPreview,
  getAIScenes,
  getAISceneTurns,
  getAIToolExecutions,
} from '@/api'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIDebugTab (t: (key: string, params?: Record<string, unknown>) => string) {
  const noticeStore = useNoticeStore()

  const loadingDebug = ref(false)
  const loadingTurns = ref(false)
  const conversations = ref<AIConversationItem[]>([])
  const turns = ref<AIConversationTurnItem[]>([])
  const toolExecutions = ref<AIToolExecutionItem[]>([])
  const promptPreview = ref<AIConversationPromptPreviewItem | null>(null)
  const selectedSceneId = ref('')
  const debugForm = reactive({
    limit: 20,
    turnLimit: 50,
  })

  const selectedConversation = computed(() => conversations.value.find(item => item.scene_id === selectedSceneId.value) ?? null)
  const latestAssistantTurn = computed(() => {
    for (let index = turns.value.length - 1; index >= 0; index -= 1) {
      const turn = turns.value[index]
      if (turn.sender_type === 'bot' && turn.content_text.trim()) {
        return turn
      }
    }
    return null
  })

  const traceIds = computed(() => {
    const values = new Set(
      turns.value
        .map(item => item.trace_id)
        .filter((value): value is string => value != null),
    )
    return [...values]
  })

  const toolExecutionStats = computed(() => ({
    success: toolExecutions.value.filter(item => item.status === 'success').length,
    error: toolExecutions.value.filter(item => item.status === 'error').length,
    timeout: toolExecutions.value.filter(item => item.status === 'timeout').length,
  }))
  const promptPreviewOperatorMemories = computed(() => (
    (promptPreview.value?.memories ?? []).filter(item => item.memory_layer === 'operator')
  ))
  const promptPreviewSummaryMemories = computed(() => (
    (promptPreview.value?.memories ?? []).filter(item => item.memory_layer === 'summary')
  ))
  const promptPreviewLongTermMemories = computed(() => (
    (promptPreview.value?.memories ?? []).filter(item => item.memory_layer === 'long_term')
  ))
  const promptPreviewKnowledgeMemories = computed(() => (
    (promptPreview.value?.memories ?? []).filter(item => item.memory_layer === 'knowledge')
  ))

  async function loadDebugData () {
    loadingDebug.value = true
    try {
      const response = await getAIScenes({ limit: debugForm.limit })
      conversations.value = response.data
      if (!selectedSceneId.value && conversations.value.length > 0) {
        selectedSceneId.value = conversations.value[0].scene_id
      }
      if (selectedSceneId.value) {
        await loadConversationDetails(selectedSceneId.value)
      } else {
        turns.value = []
        toolExecutions.value = []
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.workbenchLoadFailed')), 'error')
    } finally {
      loadingDebug.value = false
    }
  }

  async function loadConversationDetails (sceneId: string) {
    selectedSceneId.value = sceneId
    loadingTurns.value = true
    try {
      const [turnsResponse, executionsResponse, promptPreviewResponse] = await Promise.all([
        getAISceneTurns({
          scene_id: sceneId,
          limit: debugForm.turnLimit,
        }),
        getAIToolExecutions({ scene_id: sceneId }),
        getAIScenePromptPreview({
          scene_id: sceneId,
          turn_limit: debugForm.turnLimit,
        }),
      ])
      turns.value = turnsResponse.data
      toolExecutions.value = executionsResponse.data
      promptPreview.value = promptPreviewResponse.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.workbenchTurnsFailed')), 'error')
    } finally {
      loadingTurns.value = false
    }
  }

  function summarizeRawPayload (payload: Record<string, unknown> | null) {
    if (!payload) {
      return t('common.none')
    }
    const entries = Object.entries(payload)
      .filter(([key]) => key !== 'index')
      .slice(0, 4)
      .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    return entries.join(' · ') || t('common.none')
  }

  function summarizeJsonText (value: string | null) {
    if (!value) {
      return t('common.none')
    }
    try {
      const parsed = JSON.parse(value) as Record<string, unknown> | unknown[]
      if (Array.isArray(parsed)) {
        return parsed.slice(0, 3).map(item => JSON.stringify(item)).join(' · ')
      }
      return Object.entries(parsed)
        .slice(0, 4)
        .map(([key, item]) => `${key}: ${typeof item === 'object' ? JSON.stringify(item) : String(item)}`)
        .join(' · ')
    } catch {
      return value
    }
  }

  return {
    conversations,
    debugForm,
    loadConversationDetails,
    loadDebugData,
    loadingDebug,
    loadingTurns,
    latestAssistantTurn,
    promptPreviewOperatorMemories,
    promptPreview,
    promptPreviewKnowledgeMemories,
    promptPreviewLongTermMemories,
    promptPreviewSummaryMemories,
    selectedConversation,
    selectedConversationId: selectedSceneId,
    summarizeJsonText,
    summarizeRawPayload,
    toolExecutions,
    toolExecutionStats,
    traceIds,
    turns,
  }
}
