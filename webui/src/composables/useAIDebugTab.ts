import type {
  AIChatMessageItem,
  AIModelUsageSummaryItem,
  AISessionItem,
  AISessionPromptChannelsItem,
  AISessionPromptPreviewItem,
  AITurnTraceItem,
} from '@/api/ai'
import { computed, reactive, ref } from 'vue'
import {
  getAIScenePromptPreview,
  getAIScenes,
  getAISceneTurns,
  getAIUsageSummary,
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
  const promptPreview = ref<AISessionPromptPreviewItem | null>(null)
  const traces = ref<AITurnTraceItem[]>([])
  const usageByResponseSource = ref<AIModelUsageSummaryItem[]>([])
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
      const [turnsResponse, previewResponse] = await Promise.all([
        getAISceneTurns({
          limit: debugForm.turnLimit,
          scene_id: sceneId,
        }),
        getAIScenePromptPreview({
          scene_id: sceneId,
          turn_limit: debugForm.turnLimit,
        }),
      ])
      turns.value = turnsResponse.data
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
      const params = {
        commit_status: optionalTraceFilter(traceFilter.commit_status),
        limit: traceFilter.limit,
        runtime_mode: optionalTraceFilter(traceFilter.runtime_mode),
        session_id: traceFilter.session_id.trim() || undefined,
        terminal_status: optionalTraceFilter(traceFilter.terminal_status),
        trace_id: traceFilter.trace_id.trim() || undefined,
      }
      const [traceResponse, usageResponse] = await Promise.all([
        getAITurnTraces(params),
        getAIUsageSummary({
          group_by: 'response_source',
          session_id: params.session_id,
          trace_id: params.trace_id,
        }),
      ])
      traces.value = traceResponse.data
      usageByResponseSource.value = usageResponse.data
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
    summarizeRawPayload,
    traceFilter,
    traceIds,
    traces,
    turns,
    usageByResponseSource,
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
  append('response_rules', t('ai.promptChannelResponseRules'), channels.response_rules)
  append('context_priority', t('ai.promptChannelContextPriority'), channels.context_priority)
  append('persona', t('ai.promptChannelPersona'), [channels.persona])
  append('style', t('ai.promptChannelStyle'), channels.style ? [channels.style] : [])
  append('tool_policy', t('ai.promptChannelToolPolicy'), channels.tool_policy ? [channels.tool_policy] : [])
  append('expression_context', t('ai.promptChannelExpressionContext'), channels.expression_context)
  append('evidence_context', t('ai.promptChannelEvidenceContext'), channels.evidence_context)
  append('conversation_messages', t('ai.promptChannelConversationMessages'), channels.conversation_messages)
  append('instruction', t('ai.promptChannelInstruction'), [channels.instruction])
  return sections
}
