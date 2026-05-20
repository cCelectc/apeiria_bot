<script setup lang="ts">
import type {
  AuthOkPayload,
  CapabilitiesResponsePayload,
  ChatEnvelope,
  ImageSegment,
  MessageReceivePayload,
  PartialReplyCompletePayload,
  PartialReplyDeltaPayload,
  PartialReplyFailedPayload,
  PartialReplyStartPayload,
  SessionSnapshotPayload,
} from '@/types/chat'
import {
  Download,
  ImagePlus,
  Maximize2,
  Minus,
  Move,
  Plus,
  RefreshCw,
  Send,
  Trash2,
  X,
} from 'lucide-vue-next'
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ChatMessageList from '@/components/management/ChatMessageList.vue'
import { PageScaffold, StatusBadge } from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog'
import { useChatComposer } from '@/composables/useChatComposer'
import {
  formatBytes,
  useChatImagePreview,
  useProtectedChatAssets,
} from '@/composables/useChatMedia'
import { useChatSessionState } from '@/composables/useChatSessionState'
import { useChatTransport } from '@/composables/useChatTransport'
import {
  createSessionKey,
  formatSessionTime,
  formatSessionTitle,
  summarizeReplyMessage,
} from '@/utils/chatDisplay'

const { t } = useI18n()
const messagesContainer = ref<{ getElement: () => HTMLElement | null }>()

const transport = useChatTransport({
  onClose: resetConnectionState,
  onMessage: handleEnvelope,
})
const client = transport.client
const reconnect = transport.reconnect
const reconnecting = transport.reconnecting
const socketConnected = transport.socketConnected
const {
  closeImagePreview,
  downloadPreviewImage,
  handlePreviewImageLoad,
  handlePreviewWheel,
  imagePreviewAlt,
  imagePreviewSrc,
  imagePreviewVisible,
  openImagePreviewSource,
  previewImageNaturalHeight,
  previewImageNaturalWidth,
  previewImageRef,
  previewImageSizeText,
  previewImageStyle,
  previewScale,
  previewWrapRef,
  resetPreviewTransform,
  startImageDrag,
  stopImageDrag,
  togglePreviewZoom,
  zoomInPreview,
  zoomOutPreview,
} = useChatImagePreview()
const {
  buildComposerSegments,
  captureComposerSelection,
  clearComposer,
  composerHasContent,
  composerRef,
  focusComposer,
  handleComposerClick,
  handleComposerInput,
  handleComposerKeydown,
  handleComposerPaste,
  handleImageSelection,
  imageInputRef,
  isPreparingImages,
  moveComposerImageToCursor,
  openImagePreviewFromPending,
  orderedComposerImages,
  pickImages,
  removeComposerImage,
  selectComposerImage,
  selectedComposerImageId,
} = useChatComposer({
  canSend: () => chatReady.value,
  imageIndexedToken: index => t('chat.imageIndexedToken', { index: index + 1 }),
  imageReadFailed: () => t('chat.imageReadFailed'),
  imageToken: () => t('chat.imageToken'),
  onSend: () => send(),
  openImagePreviewSource,
})
const {
  openImagePreview,
  resolveImageUrl,
  revokeProtectedAssetUrls,
} = useProtectedChatAssets({
  imageAlt: () => t('chat.imageAlt'),
  openImagePreviewSource,
})
const sessionState = useChatSessionState(client, {
  clearComposer,
  closeImagePreview,
  confirmDelete: () => window.confirm(t('chat.confirmDelete')),
  createSessionKey,
  focusComposerEnd: () => focusComposer(true),
  revokeProtectedAssetUrls,
  scrollToBottom,
  socketConnected,
  t: (key, params) => t(key, params || {}),
})
const {
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
  chatReady,
  clearPendingReply,
  connected,
  deleteSessionItem,
  messages,
  pendingReply,
  pendingSessionMessage,
  recentSessions,
  saveSession,
  session,
  startNewSession,
  startReplyToMessage,
  switchToSession,
} = sessionState

void previewImageRef
void previewWrapRef
void composerRef
void imageInputRef

function resetConnectionState() {
  sessionState.resetConnectionState()
}

function handleEnvelope(event: ChatEnvelope) {
  switch (event.type) {
    case 'auth.ok':
      applyAuthOk(event.payload as AuthOkPayload)
      break
    case 'capabilities.response':
      applyCapabilities(event.payload as CapabilitiesResponsePayload)
      break
    case 'session.snapshot':
      applySessionSnapshot(event.payload as SessionSnapshotPayload)
      break
    case 'message.receive':
      appendMessage(event.payload as MessageReceivePayload)
      break
    case 'reply.partial.start':
      applyPartialReplyStart(event.payload as PartialReplyStartPayload)
      break
    case 'reply.partial.delta':
      applyPartialReplyDelta(event.payload as PartialReplyDeltaPayload)
      break
    case 'reply.partial.complete':
      applyPartialReplyComplete(event.payload as PartialReplyCompletePayload)
      break
    case 'reply.partial.failed':
      applyPartialReplyFailed(event.payload as PartialReplyFailedPayload)
      break
    case 'message.ack':
      break
    case 'message.error':
    case 'system.error': {
      const payload = event.payload as { message?: string, code?: string }
      appendSimpleMessage('error', payload.message || payload.code || t('common.unknownError'))
      break
    }
    case 'system.info':
    case 'system.warning':
      break
  }
}

function send() {
  if (!chatReady.value) {
    return
  }
  const segments = buildComposerSegments()
  if (pendingReply.value) {
    segments.unshift({
      message_id: pendingReply.value.message_id,
      text: summarizeReplyMessage(pendingReply.value, t),
      type: 'reply',
    })
  }
  if (segments.length === 0) {
    return
  }
  const messageId = `cli_${Date.now()}`
  if (session.value) {
    const result = client.sendMessage({
      message_id: messageId,
      segments,
      session_id: session.value.session_id,
    })
    if (!result.sent) {
      appendSimpleMessage('error', t('chat.sendUnavailable'))
      return
    }
  } else {
    autoCreatingSession.value = true
    pendingSessionMessage.value = {
      message_id: messageId,
      segments,
    }
    saveSession()
  }
  clearComposer()
  clearPendingReply()
}

function scrollToMessage(messageId: string) {
  const container = messagesContainer.value?.getElement()
  const target = container?.querySelector<HTMLElement>(`[data-message-id="${messageId}"]`)
  if (!target) {
    return
  }
  target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  target.classList.add('chat-message--flash')
  window.setTimeout(() => target.classList.remove('chat-message--flash'), 1600)
}

function scrollToBottom() {
  void nextTick(() => {
    const container = messagesContainer.value?.getElement()
    container?.scrollTo({
      behavior: 'smooth',
      top: container.scrollHeight,
    })
  })
}

function handleWindowKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && imagePreviewVisible.value) {
    closeImagePreview()
  }
}

function openProtectedPreview(segment: ImageSegment) {
  void openImagePreview(segment)
}

onMounted(() => {
  transport.start()
  window.addEventListener('keydown', handleWindowKeydown)
})

onUnmounted(() => {
  if (connected.value && session.value) {
    client.closeSession()
  }
  stopImageDrag()
  transport.stop()
  revokeProtectedAssetUrls()
  clearComposer()
  window.removeEventListener('keydown', handleWindowKeydown)
})
</script>

<template>
  <PageScaffold dense full-height :title="t('chat.title')">
    <template #actions>
      <StatusBadge
        :label="connected ? t('logs.connected') : t('logs.disconnected')"
        :tone="connected ? 'success' : 'error'"
      />
      <Button :disabled="reconnecting" variant="ghost" @click="reconnect">
        <RefreshCw :class="{ 'animate-spin': reconnecting }" :size="16" />
        {{ t('chat.reconnect') }}
      </Button>
      <Button :disabled="!authenticated" variant="secondary" @click="startNewSession">
        <Plus :size="16" />
        {{ t('chat.newSession') }}
      </Button>
    </template>

    <div class="chat-shell">
      <aside class="chat-sidebar">
        <div class="chat-sidebar__body">
          <div v-if="recentSessions.length > 0" class="chat-session-list">
            <article
              v-for="recent in recentSessions"
              :key="recent.session.session_id"
              class="chat-session-list__item"
              :class="{ 'chat-session-list__item--active': activeSessionId === recent.session.session_id }"
            >
              <button
                :disabled="!authenticated"
                type="button"
                @click="switchToSession(recent)"
              >
                <strong>{{ formatSessionTitle(recent, t) }}</strong>
                <span>
                  {{ formatSessionTime(recent.last_message_at || recent.session.updated_at || recent.session.created_at) || t('chat.justNow') }}
                </span>
                <small>{{ recent.last_message || t('chat.messageCount', { count: recent.message_count }) }}</small>
              </button>
              <Button
                :disabled="!authenticated"
                size="icon"
                variant="ghost"
                @click="deleteSessionItem(recent)"
              >
                <Trash2 :size="15" />
              </Button>
            </article>
          </div>
          <div v-else class="chat-sidebar__empty">
            {{ t('chat.noMessages') }}
          </div>
        </div>

        <div class="chat-sidebar__footer">
          <div class="chat-session-info">
            <div class="chat-session-info__label">{{ t('chat.sessionInfo') }}</div>
            <template v-if="activeSessionInfo">
              <div class="chat-session-info__item">
                <span>{{ t('chat.sidLabel') }}</span>
                <code>{{ activeSessionInfo.session_id }}</code>
              </div>
              <div class="chat-session-info__item">
                <span>{{ t('chat.targetLabel') }}</span>
                <strong>{{ activeSessionInfo.target_user_id }}</strong>
              </div>
            </template>
            <div v-else class="chat-session-info__empty">
              {{ t('chat.noActiveSessionInfo') }}
            </div>
          </div>
        </div>
      </aside>

      <main class="chat-panel">
        <ChatMessageList
          ref="messagesContainer"
          :messages="messages"
          :resolve-image-url="resolveImageUrl"
          @open-image-preview="openProtectedPreview"
          @reply="startReplyToMessage"
          @scroll-to-message="scrollToMessage"
        />

        <div class="chat-panel__composer">
          <div v-if="pendingReply" class="pending-reply">
            <div class="pending-reply__content">
              <div class="pending-reply__label">{{ t('chat.replyMessage') }}</div>
              <div class="pending-reply__text">
                {{ summarizeReplyMessage(pendingReply, t) }}
              </div>
            </div>
            <button
              class="pending-reply__jump"
              type="button"
              @click="scrollToMessage(pendingReply.message_id)"
            >
              {{ t('chat.viewOriginalMessage') }}
            </button>
            <Button size="icon" variant="ghost" @click="clearPendingReply">
              <X :size="15" />
            </Button>
          </div>

          <div v-if="orderedComposerImages.length > 0" class="composer-attachments">
            <article
              v-for="(image, index) in orderedComposerImages"
              :key="image.id"
              class="composer-attachment-item"
              :class="{ 'composer-attachment-item--selected': selectedComposerImageId === image.id }"
              @click="selectComposerImage(image.id)"
            >
              <div class="composer-attachment-index">
                {{ t('chat.imageIndex', { index: index + 1 }) }}
              </div>
              <img
                :alt="image.name"
                class="composer-attachment-thumb"
                :src="image.previewUrl"
                @click.stop="openImagePreviewFromPending(image)"
              >
              <div class="composer-attachment-meta">
                <div class="composer-attachment-name">{{ image.name }}</div>
                <div class="composer-attachment-size">
                  {{ formatBytes(image.size) || t('chat.imageFallback') }}
                </div>
              </div>
              <Button size="icon" variant="ghost" @click.stop="moveComposerImageToCursor(image.id)">
                <Move :size="14" />
              </Button>
              <Button size="icon" variant="ghost" @click.stop="removeComposerImage(image.id)">
                <X :size="14" />
              </Button>
            </article>
          </div>

          <div
            ref="composerRef"
            class="composer"
            :class="{ 'composer--disabled': !chatReady }"
            contenteditable="true"
            :data-placeholder="t('chat.composerPlaceholder')"
            spellcheck="false"
            @click="handleComposerClick"
            @focus="captureComposerSelection"
            @input="handleComposerInput"
            @keydown="handleComposerKeydown"
            @keyup="captureComposerSelection"
            @mouseup="captureComposerSelection"
            @paste="handleComposerPaste"
          />

          <input
            ref="imageInputRef"
            accept="image/*"
            class="chat-hidden-input"
            multiple
            type="file"
            @change="handleImageSelection"
          >

          <div class="chat-composer-actions">
            <Button
              :disabled="!chatReady || isPreparingImages || autoCreatingSession"
              variant="ghost"
              @click="pickImages"
            >
              <ImagePlus :size="16" />
              {{ t('chat.pickImage') }}
            </Button>
            <div class="chat-composer-actions__spacer" />
            <Badge v-if="isPreparingImages || autoCreatingSession" variant="secondary">
              {{ t('common.loading') }}
            </Badge>
            <Button
              :disabled="!chatReady || autoCreatingSession || !composerHasContent"
              @click="send"
            >
              <Send :size="16" />
              {{ t('common.send') }}
            </Button>
          </div>
        </div>
      </main>
    </div>

    <Dialog v-model:open="imagePreviewVisible">
      <DialogContent class="chat-preview-dialog" :show-close-button="false">
        <div class="preview-card__toolbar">
          <div class="preview-meta">
            <span>{{ t('chat.zoom', { value: Math.round(previewScale * 100) }) }}</span>
            <span v-if="previewImageNaturalWidth && previewImageNaturalHeight">
              {{ previewImageNaturalWidth }} x {{ previewImageNaturalHeight }}
            </span>
            <span v-if="previewImageSizeText">{{ previewImageSizeText }}</span>
          </div>
          <div class="preview-card__actions">
            <Button size="icon" variant="ghost" @click="zoomOutPreview"><Minus :size="16" /></Button>
            <Button size="icon" variant="ghost" @click="resetPreviewTransform"><Maximize2 :size="16" /></Button>
            <Button size="icon" variant="ghost" @click="zoomInPreview"><Plus :size="16" /></Button>
            <Button size="icon" variant="ghost" @click="downloadPreviewImage"><Download :size="16" /></Button>
            <Button size="icon" variant="ghost" @click="closeImagePreview"><X :size="16" /></Button>
          </div>
        </div>

        <div ref="previewWrapRef" class="preview-image-wrap">
          <img
            v-if="imagePreviewSrc"
            ref="previewImageRef"
            :alt="imagePreviewAlt"
            class="preview-image"
            draggable="false"
            :src="imagePreviewSrc"
            :style="previewImageStyle"
            @dblclick="togglePreviewZoom"
            @dragstart.prevent
            @load="handlePreviewImageLoad"
            @mousedown="startImageDrag"
            @wheel.prevent="handlePreviewWheel"
          >
        </div>
      </DialogContent>
    </Dialog>
  </PageScaffold>
</template>
