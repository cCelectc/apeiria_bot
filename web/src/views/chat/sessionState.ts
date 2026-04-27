import type { ChatClient } from '@/api/chat'
import type {
  CapabilitiesResponsePayload,
  ChatCapabilities,
  ChatSegment,
  ChatSessionState,
  MessageReceivePayload,
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

export function useChatSessionState (
  client: ChatClient,
  options: ChatSessionStateOptions,
) {
  const authenticated = ref(false)
  const principal = ref<WebUIPrincipal | null>(null)
  const capabilities = ref<ChatCapabilities | null>(null)
  const session = ref<ChatSessionState | null>(null)
  const recentSessions = ref<SessionListItem[]>([])
  const messages = ref<MessageReceivePayload[]>([])
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

  function appendMessage (message: MessageReceivePayload) {
    messages.value.push(message)
    options.scrollToBottom()
  }

  function appendSimpleMessage (role: 'system' | 'error', text: string) {
    appendMessage({
      session_id: session.value?.session_id ?? 'system',
      message_id: `${role}_${Date.now()}`,
      role,
      segments: [{ type: 'text', text }],
      timestamp: new Date().toISOString(),
    })
  }

  function startReplyToMessage (message: MessageReceivePayload) {
    pendingReply.value = message
    options.focusComposerEnd()
  }

  function clearPendingReply () {
    pendingReply.value = null
  }

  function resetActiveSessionState () {
    session.value = null
    draftSession.value = false
    messages.value = []
    clearPendingReply()
    options.closeImagePreview()
    options.revokeProtectedAssetUrls()
    options.clearComposer()
  }

  function resetConnectionState () {
    options.socketConnected.value = false
    authenticated.value = false
    autoCreatingSession.value = false
    pendingSessionMessage.value = null
    principal.value = null
    capabilities.value = null
    resetActiveSessionState()
  }

  function startNewSession () {
    draftSession.value = true
    autoCreatingSession.value = false
    pendingSessionMessage.value = null
    if (connected.value && session.value) {
      client.closeSession()
    }
    resetActiveSessionState()
  }

  function switchToSession (target: SessionListItem) {
    if (!authenticated.value) {
      return
    }
    if (activeSessionId.value === target.session.session_id) {
      return
    }
    draftSession.value = false
    client.selectSession({
      session_id: target.session.session_id,
    })
  }

  function deleteSessionItem (target: SessionListItem) {
    if (!authenticated.value) {
      return
    }
    const confirmed = options.confirmDelete()
    if (!confirmed) {
      return
    }
    client.deleteSession({ session_id: target.session.session_id })
  }

  function applySessionSnapshot (payload: SessionSnapshotPayload) {
    autoCreatingSession.value = false
    draftSession.value = false
    recentSessions.value = payload.sessions
    session.value = payload.active_session ?? null
    messages.value = payload.history
    const repliedMessageStillVisible = pendingReply.value
      ? payload.history.some(
          message => message.message_id === pendingReply.value?.message_id,
        )
      : false

    if (!payload.active_session) {
      clearPendingReply()
    } else if (pendingReply.value && !repliedMessageStillVisible) {
      clearPendingReply()
    }

    options.scrollToBottom()

    if (pendingSessionMessage.value && payload.active_session) {
      const pending = pendingSessionMessage.value
      pendingSessionMessage.value = null
      client.sendMessage({
        session_id: payload.active_session.session_id,
        message_id: pending.message_id,
        segments: pending.segments,
      })
    }
  }

  function applyAuthOk (payload: { principal: WebUIPrincipal }) {
    authenticated.value = true
    principal.value = payload.principal
    client.requestCapabilities()
  }

  function applyCapabilities (payload: CapabilitiesResponsePayload) {
    capabilities.value = payload.capabilities
  }

  function saveSession () {
    if (!authenticated.value) {
      return
    }
    draftSession.value = true
    const payload: SessionCreatePayload = {
      target_user_id: options.createSessionKey(),
    }
    client.createSession(payload)
  }

  return {
    activeSessionId,
    activeSessionInfo,
    applyAuthOk,
    applyCapabilities,
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
