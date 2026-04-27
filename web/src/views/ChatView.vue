<template>
  <section class="chat-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">{{ t('chat.title') }}</h1>
      </div>
      <div class="page-actions">
        <v-btn
          :loading="reconnecting"
          prepend-icon="mdi-refresh"
          variant="text"
          @click="reconnect"
        >
          {{ t('chat.reconnect') }}
        </v-btn>
        <v-btn
          :disabled="!authenticated"
          prepend-icon="mdi-plus"
          variant="tonal"
          @click="startNewSession"
        >
          {{ t('chat.newSession') }}
        </v-btn>
      </div>
    </header>

    <div class="chat-shell">
      <aside class="chat-sidebar">
        <div class="chat-sidebar__body">
          <v-list v-if="recentSessions.length > 0" class="chat-session-list" density="compact" lines="two">
            <v-list-item
              v-for="recent in recentSessions"
              :key="recent.session.session_id"
              :active="activeSessionId === recent.session.session_id"
              class="chat-session-list__item"
              :disabled="!authenticated"
              rounded="lg"
              @click="switchToSession(recent)"
            >
              <template #append>
                <v-btn
                  color="error"
                  :disabled="!authenticated"
                  icon="mdi-delete-outline"
                  size="small"
                  variant="text"
                  @click.stop="deleteSessionItem(recent)"
                />
              </template>

              <v-list-item-title class="chat-session-list__title">
                {{ formatSessionTitle(recent, t) }}
              </v-list-item-title>
              <v-list-item-subtitle>
                {{ formatSessionTime(recent.last_message_at || recent.session.updated_at || recent.session.created_at) || t('chat.justNow') }}
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>

          <div v-else class="chat-sidebar__empty">
            {{ t('chat.noMessages') }}
          </div>
        </div>

        <div class="chat-sidebar__footer">
          <div class="chat-session-info">
            <div class="chat-session-info__label">{{ t('chat.sessionInfo') }}</div>
            <template v-if="activeSessionInfo">
              <div class="chat-session-info__item">
                <span class="chat-session-info__key">{{ t('chat.sidLabel') }}</span>
                <code class="chat-session-info__value">{{ activeSessionInfo.session_id }}</code>
              </div>
              <div class="chat-session-info__item">
                <span class="chat-session-info__key">{{ t('chat.targetLabel') }}</span>
                <span class="chat-session-info__value">{{ activeSessionInfo.target_user_id }}</span>
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
          @open-image-preview="openImagePreview"
          @reply="startReplyToMessage"
          @scroll-to-message="scrollToMessage"
        />

        <div class="chat-panel__composer">
          <div v-if="pendingReply" class="pending-reply">
            <div class="pending-reply__content">
              <div class="pending-reply__label">{{ t('chat.replyMessage') }}</div>
              <div class="pending-reply__text">{{ summarizeReplyMessage(pendingReply, t) }}</div>
            </div>
            <button
              class="pending-reply__jump"
              type="button"
              @click="scrollToMessage(pendingReply.message_id)"
            >
              {{ t('chat.viewOriginalMessage') }}
            </button>
            <v-btn icon="mdi-close" size="small" variant="text" @click="clearPendingReply" />
          </div>

          <div v-if="orderedComposerImages.length > 0" class="composer-attachments">
            <div
              v-for="(image, index) in orderedComposerImages"
              :key="image.id"
              class="composer-attachment-item"
              :class="{ 'composer-attachment-item--selected': selectedComposerImageId === image.id }"
              @click="selectComposerImage(image.id)"
            >
              <div class="composer-attachment-index">{{ t('chat.imageIndex', { index: index + 1 }) }}</div>
              <img
                :alt="image.name"
                class="composer-attachment-thumb"
                :src="image.previewUrl"
                @click="openImagePreviewFromPending(image)"
              >
              <div class="composer-attachment-meta">
                <div class="composer-attachment-name">{{ image.name }}</div>
                <div class="composer-attachment-size">{{ formatBytes(image.size) || t('chat.imageFallback') }}</div>
              </div>
              <v-btn
                icon="mdi-cursor-move"
                size="x-small"
                variant="text"
                @click.stop="moveComposerImageToCursor(image.id)"
              />
              <v-btn
                icon="mdi-close"
                size="x-small"
                variant="text"
                @click.stop="removeComposerImage(image.id)"
              />
            </div>
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
            class="d-none"
            multiple
            type="file"
            @change="handleImageSelection"
          >

          <div class="chat-composer-actions">
            <v-btn
              :disabled="!chatReady || isPreparingImages || autoCreatingSession"
              variant="text"
              @click="pickImages"
            >
              {{ t('chat.pickImage') }}
            </v-btn>
            <v-spacer />
            <v-btn
              color="primary"
              :disabled="!chatReady || autoCreatingSession || !composerHasContent"
              :loading="isPreparingImages || autoCreatingSession"
              @click="send"
            >
              {{ t('common.send') }}
            </v-btn>
          </div>
        </div>
      </main>
    </div>

    <v-dialog v-model="imagePreviewVisible" max-width="1200">
      <v-card class="preview-card">
        <div class="preview-card__toolbar">
          <div class="text-caption text-medium-emphasis">
            {{ t('chat.zoom', { value: Math.round(previewScale * 100) }) }}
          </div>
          <div class="d-flex align-center ga-1">
            <v-btn icon="mdi-magnify-minus-outline" variant="text" @click="zoomOutPreview" />
            <v-btn icon="mdi-fit-to-screen-outline" variant="text" @click="resetPreviewTransform" />
            <v-btn icon="mdi-magnify-plus-outline" variant="text" @click="zoomInPreview" />
            <v-btn icon="mdi-download-outline" variant="text" @click="downloadPreviewImage" />
            <v-btn icon="mdi-close" variant="text" @click="closeImagePreview" />
          </div>
        </div>
        <div class="preview-meta text-caption text-medium-emphasis">
          <span v-if="previewImageNaturalWidth && previewImageNaturalHeight">
            {{ previewImageNaturalWidth }} × {{ previewImageNaturalHeight }}
          </span>
          <span v-if="previewImageSizeText">
            {{ previewImageSizeText }}
          </span>
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
      </v-card>
    </v-dialog>
  </section>
</template>

<script setup lang="ts">
  import type {
    AuthOkPayload,
    CapabilitiesResponsePayload,
    ChatEnvelope,
    MessageReceivePayload,
    SessionSnapshotPayload,
  } from '@/types/chat'
  import { nextTick, onMounted, onUnmounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import ChatMessageList from '@/views/chat/ChatMessageList.vue'
  import {
    formatBytes,
    useChatImagePreview,
    useProtectedChatAssets,
  } from '@/views/chat/mediaPreview'
  import {
    createSessionKey,
    formatSessionTime,
    formatSessionTitle,
    summarizeReplyMessage,
  } from '@/views/chat/messageDisplay'
  import { useChatSessionState } from '@/views/chat/sessionState'
  import { useChatTransport } from '@/views/chat/transport'
  import { useChatComposer } from '@/views/chat/useChatComposer'

  const { t } = useI18n()

  const transport = useChatTransport({
    onClose: resetConnectionState,
    onMessage: handleEnvelope,
    onOpen: client => {
      const token = localStorage.getItem('token')
      if (!token) {
        return
      }
      client.authenticate(token)
    },
  })
  const client = transport.client
  const reconnect = transport.reconnect

  const socketConnected = transport.socketConnected
  const messagesContainer = ref<{
    getElement: () => HTMLElement | null
  }>()
  const reconnecting = transport.reconnecting
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
    t,
  })
  const {
    activeSessionId,
    activeSessionInfo,
    applyAuthOk,
    applyCapabilities,
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

  function resetConnectionState () {
    sessionState.resetConnectionState()
  }

  function handleWindowKeydown (event: KeyboardEvent) {
    if (event.key === 'Escape' && imagePreviewVisible.value) {
      closeImagePreview()
    }
  }

  function handleEnvelope (event: ChatEnvelope) {
    switch (event.type) {
      case 'auth.ok': {
        applyAuthOk(event.payload as AuthOkPayload)
        break
      }
      case 'capabilities.response': {
        applyCapabilities(event.payload as CapabilitiesResponsePayload)
        break
      }
      case 'session.snapshot': {
        applySessionSnapshot(event.payload as SessionSnapshotPayload)
        break
      }
      case 'message.receive': {
        appendMessage(event.payload as MessageReceivePayload)
        break
      }
      case 'message.ack': {
        break
      }
      case 'message.error':
      case 'auth.error':
      case 'system.error': {
        const payload = event.payload as { message?: string, code?: string }
        appendSimpleMessage('error', payload.message || payload.code || t('common.unknownError'))
        break
      }
      case 'system.info':
      case 'system.warning': {
        break
      }
    }
  }

  function send () {
    if (!chatReady.value) return
    const segments = buildComposerSegments()
    if (pendingReply.value) {
      segments.unshift({
        type: 'reply',
        message_id: pendingReply.value.message_id,
        text: summarizeReplyMessage(pendingReply.value, t),
      })
    }
    if (segments.length === 0) return
    const messageId = `cli_${Date.now()}`
    if (session.value) {
      const result = client.sendMessage({
        session_id: session.value.session_id,
        message_id: messageId,
        segments,
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

  function scrollToMessage (messageId: string) {
    const container = messagesContainer.value?.getElement()
    if (!container) return

    const target = container.querySelector<HTMLElement>(`[data-message-id="${messageId}"]`)
    if (!target) return

    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    target.classList.add('chat-message--flash')
    window.setTimeout(() => {
      target.classList.remove('chat-message--flash')
    }, 1600)
  }

  function scrollToBottom () {
    nextTick(() => {
      const container = messagesContainer.value?.getElement()
      container?.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth',
      })
    })
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

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  gap: var(--stack-gap);
  height: calc(100dvh - 48px);
  min-height: 680px;
  overflow: hidden;
}

.chat-shell {
  min-height: 0;
  flex: 1;
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 14px;
}

.chat-sidebar,
.chat-panel {
  min-height: 0;
  background: rgb(var(--v-theme-surface-container-low));
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 4px 12px rgba(15, 23, 42, 0.05);
}

.chat-sidebar {
  display: flex;
  flex-direction: column;
  border-radius: var(--shape-large);
  overflow: hidden;
}

.chat-sidebar__body {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 8px 10px;
}

.chat-sidebar__footer {
  border-top: 1px solid rgba(var(--v-theme-outline-variant), 0.5);
  padding: 10px;
  background: rgb(var(--v-theme-surface-container-low));
}

.chat-session-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 152px;
  padding: 10px 12px;
  border-radius: var(--shape-base);
  background: rgb(var(--v-theme-surface-container));
}

.chat-session-info__label {
  font-size: 0.78rem;
  font-weight: 700;
  color: rgba(var(--v-theme-on-surface), 0.64);
}

.chat-session-info__item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.chat-session-info__key {
  font-size: 0.72rem;
  color: rgba(var(--v-theme-on-surface), 0.52);
}

.chat-session-info__value {
  font-size: 0.84rem;
  line-height: 1.35;
  color: rgb(var(--v-theme-on-surface));
  word-break: break-all;
}

.chat-session-info__empty {
  margin: auto 0;
  font-size: 0.78rem;
  line-height: 1.45;
  color: rgba(var(--v-theme-on-surface), 0.54);
}

.chat-sidebar__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  color: rgba(var(--v-theme-on-surface), 0.56);
  text-align: center;
  padding: 16px;
}

.chat-session-list {
  padding: 0;
  background: transparent;
}

.chat-session-list__item {
  margin-bottom: 6px;
  min-height: 58px;
  background: rgb(var(--v-theme-surface-container));
  transition:
    transform var(--motion-base) var(--motion-ease),
    background var(--motion-base) var(--motion-ease),
    box-shadow var(--motion-base) var(--motion-ease);
}

.chat-session-list__item:hover {
  background: rgb(var(--v-theme-surface-container-high));
}

.chat-session-list__item:focus-within {
  box-shadow: var(--focus-ring);
}

:deep(.chat-session-list__item .v-list-item__overlay) {
  opacity: 0.05;
}

:deep(.chat-session-list__item .v-list-item__content) {
  padding-right: 6px;
}

:deep(.chat-session-list__item .v-list-item__append) {
  margin-inline-start: 6px;
  align-self: center;
}

:deep(.chat-session-list__item .v-list-item__append .v-btn) {
  margin-inline-end: -4px;
}

.chat-session-list__title,
.chat-session-list__meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-session-list__title {
  font-weight: 600;
  font-size: 0.9rem;
  letter-spacing: -0.01em;
}

:deep(.chat-session-list__item .v-list-item-subtitle) {
  font-size: 0.76rem;
  line-height: 1.2;
}

:deep(.chat-session-list__item.v-list-item--active) {
  background: rgb(var(--v-theme-secondary-container));
  color: rgb(var(--v-theme-on-secondary-container));
}

.chat-panel {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  border-radius: var(--shape-large);
  overflow: hidden;
}

.chat-panel__composer {
  border-top: 1px solid rgba(var(--v-theme-outline-variant), 0.72);
  background: rgb(var(--v-theme-surface-container-low));
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pending-reply {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--shape-small);
  background: rgb(var(--v-theme-secondary-container));
}

.pending-reply__content {
  flex: 1;
  min-width: 0;
}

.pending-reply__label {
  font-size: 0.74rem;
  font-weight: 700;
  color: rgb(var(--v-theme-on-secondary-container));
}

.pending-reply__text {
  color: rgba(var(--v-theme-on-secondary-container), 0.76);
  font-size: 0.8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pending-reply__jump {
  border: 0;
  background: transparent;
  padding: 0;
  color: rgba(var(--v-theme-on-secondary-container), 0.82);
  font-size: 0.72rem;
  cursor: pointer;
  white-space: nowrap;
}

.pending-reply__jump:hover {
  text-decoration: underline;
}

.pending-reply__jump:focus-visible {
  outline: none;
  text-decoration: underline;
}

.composer-attachments {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.composer-attachment-item {
  flex: 0 0 204px;
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--shape-medium);
  background: rgb(var(--v-theme-surface-container));
  cursor: pointer;
  transition:
    background-color var(--motion-fast) var(--motion-ease),
    box-shadow var(--motion-fast) var(--motion-ease),
    transform var(--motion-fast) var(--motion-ease);
}

.composer-attachment-item:hover {
  background: rgb(var(--v-theme-surface-container-high));
  transform: translateY(-1px);
}

.composer-attachment-item:focus-within {
  box-shadow: var(--focus-ring);
}

.composer-attachment-item--selected {
  background: rgb(var(--v-theme-secondary-container));
}

.composer-attachment-index {
  grid-column: 1 / -1;
  font-size: 0.78rem;
  color: rgba(var(--v-theme-on-surface), 0.56);
}

.composer-attachment-thumb {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: var(--shape-small);
  cursor: zoom-in;
}

.composer-attachment-meta {
  min-width: 0;
}

.composer-attachment-name,
.composer-attachment-size {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.composer-attachment-name {
  font-size: 0.9rem;
  font-weight: 600;
}

.composer-attachment-size {
  color: rgba(var(--v-theme-on-surface), 0.6);
  font-size: 0.8rem;
}

.composer {
  min-height: 108px;
  max-height: 188px;
  overflow: auto;
  padding: 10px 12px;
  border-radius: var(--shape-medium);
  background: rgb(var(--v-theme-surface-container-high));
  line-height: 1.58;
  outline: none;
  white-space: pre-wrap;
  word-break: break-word;
}

.composer--disabled {
  opacity: 0.6;
}

.composer:empty::before {
  content: attr(data-placeholder);
  color: rgba(var(--v-theme-on-surface), 0.42);
}

.chat-composer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

:deep(.composer-image-token),
:deep(.composer-mention-token) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 2px 4px 2px 0;
  padding: 2px 6px 2px 8px;
  border-radius: var(--shape-pill);
  vertical-align: middle;
  background: rgb(var(--v-theme-secondary-container));
  color: rgb(var(--v-theme-on-secondary-container));
}

:deep(.composer-image-token--selected) {
  box-shadow: 0 0 0 2px rgba(var(--v-theme-secondary), 0.12);
}

:deep(.composer-image-token__label),
:deep(.composer-mention-token__label) {
  font-size: 0.85rem;
  line-height: 1.4;
}

:deep(.composer-image-token__remove),
:deep(.composer-mention-token__remove) {
  border: 0;
  padding: 0;
  width: 18px;
  height: 18px;
  border-radius: var(--shape-pill);
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.preview-card {
  padding: 8px;
}

.preview-card__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 8px 0;
}

.preview-meta {
  display: flex;
  gap: 12px;
  padding: 0 16px 8px;
}

.preview-image-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: min(78vh, 860px);
  overflow: hidden;
  border-radius: var(--shape-medium);
  background: rgb(var(--v-theme-surface-container));
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  user-select: none;
}

@media (max-width: 1100px) {
  .chat-shell {
    grid-template-columns: 220px minmax(0, 1fr);
  }
}

@media (max-width: 900px) {
  .chat-page {
    height: auto;
    min-height: 0;
    overflow: visible;
  }

  .chat-shell {
    grid-template-columns: 1fr;
    height: auto;
  }

  .chat-sidebar {
    max-height: 280px;
  }

  .chat-panel {
    min-height: 70vh;
  }

  .chat-bubble {
    max-width: 100%;
  }
}
</style>
