import type { ChatClient, ChatSendResult } from '@/api/chat'
import type {
  CapabilitiesResponsePayload,
  ChatCapabilities,
  ChatSegment,
  ChatSessionState,
  MessageReceivePayload,
  PartialReplyCompletePayload,
  PartialReplyDeltaPayload,
  PartialReplyFailedPayload,
  PartialReplyStartPayload,
  SessionCreatePayload,
  SessionListItem,
  SessionSnapshotPayload,
  WebUIPrincipal,
} from '@/types/chat'
import { computed, type Ref, ref } from 'vue'

interface ChatSessionStateOptions {
  clearComposer: () => void
  closeImagePreview: () => void
  confirmDelete: () => boolean
  createSessionKey: () => string
  focusComposerEnd: () => void
  revokeProtectedAssetUrls: () => void
  scrollToBottom: () => void
  socketConnected: Ref<boolean>
  t: (key: string, params?: Record<string, unknown>) => string
}

export function useChatSessionState(
  client: ChatClient,
  options: ChatSessionStateOptions,
) {
  const authenticated = ref(false)
  const principal = ref<WebUIPrincipal | null>(null)
  const capabilities = ref<ChatCapabilities | null>(null)
  const session = ref<ChatSessionState | null>(null)
  const recentSessions = ref<SessionListItem[]>([])
  const messages = ref<MessageReceivePayload[]>([])
  const partialReplies = new Map<string, MessageReceivePayload>()
  const pendingReply = ref<MessageReceivePayload | null>(null)
  const autoCreatingSession = ref(false)
  const draftSession = ref(false)
  const pendingSessionMessage = ref<{
    message_id: string
    segments: ChatSegment[]
  } | null>(null)

  const connected = computed(() => options.socketConnected.value && authenticated.value)
  const chatReady = computed(() => connected.value)
  const activeSessionInfo = computed(() => (draftSession.value ? null : session.value))
  const activeSessionId = computed(() => activeSessionInfo.value?.session_id || '')

  function appendMessage(message: MessageReceivePayload) {
    if (message.trace_id) {
      for (const [streamId, pending] of partialReplies) {
        if (pending.trace_id === message.trace_id) {
          partialReplies.delete(streamId)
          messages.value = messages.value.filter(item => item.message_id !== pending.message_id)
          break
        }
      }
    }
    messages.value.push(message)
    options.scrollToBottom()
  }

  function appendSimpleMessage(role: 'system' | 'error', text: string) {
    appendMessage({
      message_id: `${role}_${Date.now()}`,
      role,
      segments: [{ type: 'text', text }],
      session_id: session.value?.session_id ?? 'system',
      timestamp: new Date().toISOString(),
    })
  }

  function applyPartialReplyStart(payload: PartialReplyStartPayload) {
    if (payload.session_id !== activeSessionId.value) {
      return
    }
    const pending: MessageReceivePayload = {
      message_id: `partial_${payload.stream_id}`,
      role: 'bot',
      segments: [{ type: 'text', text: '' }],
      session_id: payload.session_id,
      timestamp: new Date().toISOString(),
      trace_id: payload.trace_id,
    }
    partialReplies.set(payload.stream_id, pending)
    messages.value.push(pending)
    options.scrollToBottom()
  }

  function applyPartialReplyDelta(payload: PartialReplyDeltaPayload) {
    const pending = partialReplies.get(payload.stream_id)
    if (!pending || pending.session_id !== payload.session_id) {
      return
    }
    const first = pending.segments[0]
    if (first?.type === 'text') {
      first.text += payload.content_delta
    }
    messages.value = [...messages.value]
    options.scrollToBottom()
  }

  function applyPartialReplyComplete(payload: PartialReplyCompletePayload) {
    const pending = partialReplies.get(payload.stream_id)
    if (!pending) {
      return
    }
    partialReplies.delete(payload.stream_id)
    if (payload.message_id) {
      messages.value = messages.value.filter(item => item.message_id !== pending.message_id)
    }
  }

  function applyPartialReplyFailed(payload: PartialReplyFailedPayload) {
    const pending = partialReplies.get(payload.stream_id)
    if (!pending) {
      return
    }
    partialReplies.delete(payload.stream_id)
    messages.value = messages.value.filter(item => item.message_id !== pending.message_id)
    if (payload.message) {
      appendSimpleMessage('error', payload.message)
    }
  }

  function handleSendResult(result: ChatSendResult) {
    if (result.sent) {
      return true
    }
    appendSimpleMessage('error', options.t('chat.sendUnavailable'))
    return false
  }

  function startReplyToMessage(message: MessageReceivePayload) {
    pendingReply.value = message
    options.focusComposerEnd()
  }

  function clearPendingReply() {
    pendingReply.value = null
  }

  function resetActiveSessionState() {
    session.value = null
    draftSession.value = false
    messages.value = []
    partialReplies.clear()
    clearPendingReply()
    options.closeImagePreview()
    options.revokeProtectedAssetUrls()
    options.clearComposer()
  }

  function resetConnectionState() {
    options.socketConnected.value = false
    authenticated.value = false
    autoCreatingSession.value = false
    pendingSessionMessage.value = null
    principal.value = null
    capabilities.value = null
    resetActiveSessionState()
  }

  function startNewSession() {
    draftSession.value = true
    autoCreatingSession.value = false
    pendingSessionMessage.value = null
    if (connected.value && session.value && !handleSendResult(client.closeSession())) {
      return
    }
    resetActiveSessionState()
  }

  function switchToSession(target: SessionListItem) {
    if (!authenticated.value || activeSessionId.value === target.session.session_id) {
      return
    }
    draftSession.value = false
    handleSendResult(client.selectSession({ session_id: target.session.session_id }))
  }

  function deleteSessionItem(target: SessionListItem) {
    if (!authenticated.value || !options.confirmDelete()) {
      return
    }
    handleSendResult(client.deleteSession({ session_id: target.session.session_id }))
  }

  function applySessionSnapshot(payload: SessionSnapshotPayload) {
    autoCreatingSession.value = false
    draftSession.value = false
    recentSessions.value = payload.sessions
    session.value = payload.active_session ?? null
    messages.value = payload.history
    partialReplies.clear()
    const repliedMessageStillVisible = pendingReply.value
      ? payload.history.some(
          message => message.message_id === pendingReply.value?.message_id,
        )
      : false
    if (!payload.active_session || (pendingReply.value && !repliedMessageStillVisible)) {
      clearPendingReply()
    }
    options.scrollToBottom()

    if (pendingSessionMessage.value && payload.active_session) {
      const pending = pendingSessionMessage.value
      pendingSessionMessage.value = null
      handleSendResult(client.sendMessage({
        message_id: pending.message_id,
        segments: pending.segments,
        session_id: payload.active_session.session_id,
      }))
    }
  }

  function applyAuthOk(payload: { principal: WebUIPrincipal }) {
    authenticated.value = true
    principal.value = payload.principal
    handleSendResult(client.requestCapabilities())
  }

  function applyCapabilities(payload: CapabilitiesResponsePayload) {
    capabilities.value = payload.capabilities
  }

  function saveSession() {
    if (!authenticated.value) {
      return
    }
    draftSession.value = true
    const payload: SessionCreatePayload = {
      target_user_id: options.createSessionKey(),
    }
    if (!handleSendResult(client.createSession(payload))) {
      draftSession.value = false
      autoCreatingSession.value = false
      pendingSessionMessage.value = null
    }
  }

  return {
    activeSessionId,
    activeSessionInfo,
    applyAuthOk,
    applyCapabilities,
    applyPartialReplyComplete,
    applyPartialReplyDelta,
    applyPartialReplyFailed,
    applyPartialReplyStart,
    applySessionSnapshot,
    appendMessage,
    appendSimpleMessage,
    authenticated,
    autoCreatingSession,
    capabilities,
    chatReady,
    clearPendingReply,
    connected,
    deleteSessionItem,
    draftSession,
    messages,
    pendingReply,
    pendingSessionMessage,
    principal,
    recentSessions,
    resetConnectionState,
    saveSession,
    session,
    startNewSession,
    startReplyToMessage,
    switchToSession,
  }
}
