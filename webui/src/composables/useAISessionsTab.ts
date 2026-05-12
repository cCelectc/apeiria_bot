import type {
  AIManagedSessionDetailItem,
  AIManagedSessionItem,
  AIPersonaItem,
} from '@/api/ai'
import { computed, reactive, ref } from 'vue'
import {
  getAIManagedSession,
  getAIManagedSessions,
  getAIPersonas,
  resetAIManagedSessionContext,
  updateAIManagedSessionEnabled,
  updateAIManagedSessionPersona,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

const ALL_FILTER = '__all__'
const UNASSIGNED_PERSONA = '__none__'

export function useAISessionsTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const sessions = ref<AIManagedSessionItem[]>([])
  const personas = ref<AIPersonaItem[]>([])
  const selectedSessionId = ref('')
  const selectedDetail = ref<AIManagedSessionDetailItem | null>(null)
  const loadingSessions = ref(false)
  const loadingDetail = ref(false)
  const savingEnabled = ref(false)
  const savingPersona = ref(false)
  const resettingContext = ref(false)
  const filters = reactive({
    enabled: ALL_FILTER,
    limit: 50,
    messageLimit: 50,
    query: '',
  })

  const filteredSessions = computed(() => {
    const keyword = filters.query.trim().toLowerCase()
    return sessions.value.filter(item => {
      if (filters.enabled === 'enabled' && !item.ai_enabled) {
        return false
      }
      if (filters.enabled === 'disabled' && item.ai_enabled) {
        return false
      }
      if (!keyword) {
        return true
      }
      return sessionSearchText(item).toLowerCase().includes(keyword)
    })
  })
  const selectedSession = computed(() => (
    sessions.value.find(item => item.session_id === selectedSessionId.value) ?? null
  ))
  const personaSelection = computed(() => (
    selectedDetail.value?.persona?.persona_id ?? UNASSIGNED_PERSONA
  ))
  const enabledCount = computed(() => sessions.value.filter(item => item.ai_enabled).length)
  const disabledCount = computed(() => sessions.value.length - enabledCount.value)

  async function loadSessions() {
    loadingSessions.value = true
    try {
      const [sessionsResponse, personasResponse] = await Promise.all([
        getAIManagedSessions({ limit: filters.limit }),
        getAIPersonas(),
      ])
      sessions.value = sessionsResponse.data
      personas.value = personasResponse.data
      if (
        selectedSessionId.value
        && !sessions.value.some(item => item.session_id === selectedSessionId.value)
      ) {
        selectedSessionId.value = ''
        selectedDetail.value = null
      }
      if (!selectedSessionId.value && sessions.value.length > 0) {
        selectedSessionId.value = sessions.value[0].session_id
      }
      if (selectedSessionId.value) {
        await loadSessionDetail(selectedSessionId.value)
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.sessionLoadFailed')), 'error')
    } finally {
      loadingSessions.value = false
    }
  }

  async function loadSessionDetail(sessionId: string) {
    selectedSessionId.value = sessionId
    loadingDetail.value = true
    try {
      const response = await getAIManagedSession(sessionId, {
        message_limit: filters.messageLimit,
      })
      selectedDetail.value = response.data
      upsertSessionFromDetail(response.data)
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.sessionDetailFailed')), 'error')
    } finally {
      loadingDetail.value = false
    }
  }

  async function refreshSelectedDetail() {
    if (!selectedSessionId.value) {
      return
    }
    await loadSessionDetail(selectedSessionId.value)
  }

  async function setAIEnabled(nextValue: boolean) {
    if (!selectedSessionId.value || savingEnabled.value) {
      return
    }
    savingEnabled.value = true
    try {
      const response = await updateAIManagedSessionEnabled(
        selectedSessionId.value,
        nextValue,
      )
      selectedDetail.value = response.data
      upsertSessionFromDetail(response.data)
      noticeStore.show(t('ai.sessionUpdated'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.sessionUpdateFailed')), 'error')
    } finally {
      savingEnabled.value = false
    }
  }

  async function setSessionPersona(nextPersonaId: string) {
    if (!selectedSessionId.value || savingPersona.value) {
      return
    }
    savingPersona.value = true
    try {
      const response = await updateAIManagedSessionPersona(
        selectedSessionId.value,
        nextPersonaId === UNASSIGNED_PERSONA ? null : nextPersonaId,
      )
      selectedDetail.value = response.data
      upsertSessionFromDetail(response.data)
      noticeStore.show(t('ai.sessionUpdated'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.sessionUpdateFailed')), 'error')
    } finally {
      savingPersona.value = false
    }
  }

  async function resetContext() {
    if (!selectedSessionId.value || resettingContext.value) {
      return
    }
    resettingContext.value = true
    try {
      const response = await resetAIManagedSessionContext(selectedSessionId.value)
      selectedDetail.value = response.data
      upsertSessionFromDetail(response.data)
      noticeStore.show(t('ai.sessionResetDone'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.sessionResetFailed')), 'error')
    } finally {
      resettingContext.value = false
    }
  }

  function upsertSessionFromDetail(detail: AIManagedSessionDetailItem) {
    const index = sessions.value.findIndex(item => item.session_id === detail.session_id)
    const existing = index >= 0 ? sessions.value[index] : null
    const nextItem: AIManagedSessionItem = {
      ai_enabled: detail.ai_enabled,
      diagnostic_count: existing?.diagnostic_count ?? detail.trace_entries.length,
      last_message_at: existing?.last_message_at ?? detail.recent_messages.at(-1)?.created_at ?? null,
      last_observed_at: existing?.last_observed_at ?? detail.recent_messages.at(-1)?.created_at ?? null,
      message_count: existing?.message_count ?? detail.recent_messages.length,
      message_type: detail.message_type,
      persona: detail.persona,
      platform_id: detail.platform_id,
      platform_type: detail.platform_type,
      session_id: detail.session_id,
      source_labels: detail.source_labels,
      subject_id: detail.subject_id,
    }
    if (index >= 0) {
      sessions.value.splice(index, 1, nextItem)
    } else {
      sessions.value.unshift(nextItem)
    }
  }

  return {
    ALL_FILTER,
    UNASSIGNED_PERSONA,
    disabledCount,
    enabledCount,
    filteredSessions,
    filters,
    loadSessionDetail,
    loadSessions,
    loadingDetail,
    loadingSessions,
    personaSelection,
    personas,
    refreshSelectedDetail,
    resetContext,
    resettingContext,
    savingEnabled,
    savingPersona,
    selectedDetail,
    selectedSession,
    selectedSessionId,
    sessions,
    setAIEnabled,
    setSessionPersona,
  }
}

function sessionSearchText(item: AIManagedSessionItem) {
  return [
    item.session_id,
    item.platform_id,
    item.platform_type,
    item.message_type,
    item.subject_id,
    item.persona?.name,
    ...Object.values(item.source_labels),
  ]
    .filter((value): value is string => typeof value === 'string' && value.length > 0)
    .join(' ')
}
