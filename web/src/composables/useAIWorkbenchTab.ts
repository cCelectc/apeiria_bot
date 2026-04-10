import type { AIConversationItem, AIConversationTurnItem, AIToolExecutionItem } from '@/api'
import { computed, reactive, ref } from 'vue'
import { getAIConversations, getAIConversationTurns, getAIToolExecutions } from '@/api'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIWorkbenchTab (t: (key: string, params?: Record<string, unknown>) => string) {
  const noticeStore = useNoticeStore()

  const loadingWorkbench = ref(false)
  const loadingTurns = ref(false)
  const conversations = ref<AIConversationItem[]>([])
  const turns = ref<AIConversationTurnItem[]>([])
  const toolExecutions = ref<AIToolExecutionItem[]>([])
  const selectedConversationId = ref('')
  const workbenchForm = reactive({
    limit: 20,
    turnLimit: 50,
  })

  const selectedConversation = computed(() => conversations.value.find(item => item.conversation_id === selectedConversationId.value) ?? null)

  const traceIds = computed(() => {
    const values = new Set(
      turns.value
        .map(item => item.trace_id)
        .filter((value): value is string => value != null),
    )
    return [...values]
  })

  async function loadWorkbenchData () {
    loadingWorkbench.value = true
    try {
      const response = await getAIConversations({ limit: workbenchForm.limit })
      conversations.value = response.data
      if (!selectedConversationId.value && conversations.value.length > 0) {
        selectedConversationId.value = conversations.value[0].conversation_id
      }
      if (selectedConversationId.value) {
        await loadConversationDetails(selectedConversationId.value)
      } else {
        turns.value = []
        toolExecutions.value = []
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.workbenchLoadFailed')), 'error')
    } finally {
      loadingWorkbench.value = false
    }
  }

  async function loadConversationDetails (conversationId: string) {
    selectedConversationId.value = conversationId
    loadingTurns.value = true
    try {
      const [turnsResponse, executionsResponse] = await Promise.all([
        getAIConversationTurns({
          conversation_id: conversationId,
          limit: workbenchForm.turnLimit,
        }),
        getAIToolExecutions({ conversation_id: conversationId }),
      ])
      turns.value = turnsResponse.data
      toolExecutions.value = executionsResponse.data
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

  return {
    conversations,
    loadConversationDetails,
    loadWorkbenchData,
    loadingTurns,
    loadingWorkbench,
    selectedConversation,
    selectedConversationId,
    summarizeRawPayload,
    toolExecutions,
    traceIds,
    turns,
    workbenchForm,
  }
}
