import type {
  AIChatMessageItem,
  AISessionItem,
  AISessionPromptChannelsItem,
  AISessionPromptPreviewItem,
  AIToolExecutionItem,
  AITurnTraceItem,
} from '@/api/ai'
import { computed, reactive, ref } from 'vue'
import {
  getAIScenePromptPreview,
  getAIScenes,
  getAISceneTurns,
  getAIToolExecutions,
  getAITurnTraces,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export interface PromptChannelSection {
  key: string
  lines: string[]
  title: string
}

export function useAIDebugTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const loadingDebug = ref(false)
  const loadingTurns = ref(false)
  const loadingTraces = ref(false)
  const conversations = ref<AISessionItem[]>([])
  const turns = ref<AIChatMessageItem[]>([])
  const toolExecutions = ref<AIToolExecutionItem[]>([])
  const promptPreview = ref<AISessionPromptPreviewItem | null>(null)
  const traces = ref<AITurnTraceItem[]>([])
  const selectedSceneId = ref('')
  const debugForm = reactive({
    limit: 20,
    turnLimit: 50,
  })
  const traceFilter = reactive({
    commit_status: '__all__',
    limit: 20,
    runtime_mode: '__all__',
    session_id: '',
    terminal_status: '__all__',
    trace_id: '',
  })

  const selectedConversation = computed(() => (
    conversations.value.find(item => item.session_id === selectedSceneId.value) ?? null
  ))
  const latestAssistantTurn = computed(() => {
    for (let index = turns.value.length - 1; index >= 0; index -= 1) {
      const turn = turns.value[index]
      if (turn.author_role === 'assistant' && turn.text_content.trim()) {
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
    failed: toolExecutions.value.filter(item => (
      ['error', 'failed', 'timeout', 'denied', 'not_ready'].includes(item.status)
    )).length,
    success: toolExecutions.value.filter(item => item.status === 'success').length,
    timeout: toolExecutions.value.filter(item => item.status === 'timeout').length,
  }))
  const planningPromptChannelSections = computed(() => (
    buildPromptChannelSections(promptPreview.value?.planning_channels, t)
  ))
  const roleplayPromptChannelSections = computed(() => (
    buildPromptChannelSections(promptPreview.value?.roleplay_channels, t)
  ))

  async function loadDebugData() {
    loadingDebug.value = true
    try {
      const response = await getAIScenes({ limit: debugForm.limit })
      conversations.value = response.data
      if (!selectedSceneId.value && conversations.value.length > 0) {
        selectedSceneId.value = conversations.value[0].session_id
      }
      if (selectedSceneId.value) {
        await loadConversationDetails(selectedSceneId.value)
      } else {
        turns.value = []
        toolExecutions.value = []
        promptPreview.value = null
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.workbenchLoadFailed')), 'error')
    } finally {
      loadingDebug.value = false
    }
  }

  async function loadConversationDetails(sceneId: string) {
    selectedSceneId.value = sceneId
    traceFilter.session_id = sceneId
    loadingTurns.value = true
    try {
      const [turnsResponse, executionsResponse, previewResponse] = await Promise.all([
        getAISceneTurns({
          limit: debugForm.turnLimit,
          scene_id: sceneId,
        }),
        getAIToolExecutions({ scene_id: sceneId }),
        getAIScenePromptPreview({
          scene_id: sceneId,
          turn_limit: debugForm.turnLimit,
        }),
      ])
      turns.value = turnsResponse.data
      toolExecutions.value = executionsResponse.data
      promptPreview.value = previewResponse.data
      await loadTraces()
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.workbenchTurnsFailed')), 'error')
    } finally {
      loadingTurns.value = false
    }
  }

  async function loadTraces() {
    loadingTraces.value = true
    try {
      const response = await getAITurnTraces({
        commit_status: optionalTraceFilter(traceFilter.commit_status),
        limit: traceFilter.limit,
        runtime_mode: optionalTraceFilter(traceFilter.runtime_mode),
        session_id: traceFilter.session_id.trim() || undefined,
        terminal_status: optionalTraceFilter(traceFilter.terminal_status),
        trace_id: traceFilter.trace_id.trim() || undefined,
      })
      traces.value = response.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.workbenchLoadFailed')), 'error')
    } finally {
      loadingTraces.value = false
    }
  }

  function summarizeRawPayload(payload: Record<string, unknown> | null) {
    if (!payload) {
      return t('common.none')
    }
    return Object.entries(payload)
      .filter(([key]) => key !== 'index')
      .slice(0, 4)
      .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
      .join(' / ') || t('common.none')
  }

  function summarizeJsonText(value: string | null) {
    if (!value) {
      return t('common.none')
    }
    try {
      const parsed = JSON.parse(value) as Record<string, unknown> | unknown[]
      if (Array.isArray(parsed)) {
        return parsed.slice(0, 3).map(item => JSON.stringify(item)).join(' / ')
      }
      return Object.entries(parsed)
        .slice(0, 4)
        .map(([key, item]) => `${key}: ${typeof item === 'object' ? JSON.stringify(item) : String(item)}`)
        .join(' / ')
    } catch {
      return value
    }
  }

  return {
    conversations,
    debugForm,
    latestAssistantTurn,
    loadConversationDetails,
    loadDebugData,
    loadTraces,
    loadingDebug,
    loadingTraces,
    loadingTurns,
    planningPromptChannelSections,
    promptPreview,
    roleplayPromptChannelSections,
    selectedConversation,
    selectedConversationId: selectedSceneId,
    summarizeJsonText,
    summarizeRawPayload,
    toolExecutions,
    toolExecutionStats,
    traceFilter,
    traceIds,
    traces,
    turns,
  }
}

function optionalTraceFilter(value: string) {
  return value === '__all__' ? undefined : value
}

function buildPromptChannelSections(
  channels: AISessionPromptChannelsItem | null | undefined,
  t: (key: string) => string,
): PromptChannelSection[] {
  if (!channels) {
    return []
  }
  const sections: PromptChannelSection[] = []
  const append = (key: string, title: string, lines: string[] | null | undefined) => {
    const normalizedLines = (lines ?? []).map(line => line.trim()).filter(Boolean)
    if (normalizedLines.length > 0) {
      sections.push({ key, lines: normalizedLines, title })
    }
  }
  append('system_instructions', t('ai.promptChannelSystemInstructions'), channels.system_instructions)
  append('persona', t('ai.promptChannelPersona'), [channels.persona])
  append('style', t('ai.promptChannelStyle'), channels.style ? [channels.style] : [])
  append('relationship', t('ai.promptChannelRelationship'), channels.relationship ? [channels.relationship] : [])
  append('person_profile', t('ai.promptChannelPersonProfile'), channels.person_profile)
  append('social_policy', t('ai.promptChannelSocialPolicy'), channels.social_policy ? [channels.social_policy] : [])
  append('tool_policy', t('ai.promptChannelToolPolicy'), channels.tool_policy ? [channels.tool_policy] : [])
  append('future_task', t('ai.promptChannelFutureTask'), channels.future_task ? [channels.future_task] : [])
  append('tool_results', t('ai.promptChannelToolResults'), channels.tool_results)
  append('operator_memories', t('ai.promptChannelOperatorMemories'), channels.operator_memories)
  append('summary_memories', t('ai.promptChannelSummaryMemories'), channels.summary_memories)
  append('long_term_memories', t('ai.promptChannelLongTermMemories'), channels.long_term_memories)
  append('knowledge_memories', t('ai.promptChannelKnowledgeMemories'), channels.knowledge_memories)
  append('conversation_summary', t('ai.promptChannelConversationSummary'), channels.conversation_summary ? [channels.conversation_summary] : [])
  append('context_priority', t('ai.promptChannelContextPriority'), channels.context_priority)
  append('conversation_messages', t('ai.promptChannelConversationMessages'), channels.conversation_messages)
  append('response_rules', t('ai.promptChannelResponseRules'), channels.response_rules)
  append('instruction', t('ai.promptChannelInstruction'), [channels.instruction])
  return sections
}
