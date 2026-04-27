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
        <div ref="messagesContainer" class="chat-panel__messages">
          <div v-if="messages.length === 0" class="chat-empty">
            <div class="chat-empty__title">{{ t('chat.newSession') }}</div>
          </div>

          <div
            v-for="message in messages"
            :key="message.message_id + message.timestamp"
            class="chat-message"
            :data-message-id="message.message_id"
          >
            <div v-if="message.role === 'system'" class="chat-message-row chat-message-row--system">
              <v-chip color="grey" size="small" variant="tonal">
                {{ getTextContent(message.segments, t) }}
              </v-chip>
            </div>

            <div v-else-if="message.role === 'error'" class="chat-message-row chat-message-row--bot">
              <div class="chat-message-stack chat-message-stack--bot">
                <v-card class="chat-bubble chat-bubble--error" color="error" rounded="lg" variant="tonal">
                  <template v-for="(segment, index) in message.segments" :key="index">
                    <div v-if="segment.type === 'text'" class="text-body-2">{{ segment.text }}</div>
                  </template>
                </v-card>
              </div>
            </div>

            <div v-else :class="message.role === 'user' ? 'chat-message-row chat-message-row--user' : 'chat-message-row chat-message-row--bot'">
              <div
                class="chat-message-stack"
                :class="message.role === 'user' ? 'chat-message-stack--user' : 'chat-message-stack--bot'"
              >
                <v-card
                  class="chat-bubble"
                  :class="{
                    'chat-bubble--user': message.role === 'user',
                    'chat-bubble--bot': message.role === 'bot',
                    'chat-bubble--image': hasImageSegment(message.segments),
                  }"
                  rounded="lg"
                  :variant="message.role === 'user' ? 'flat' : 'flat'"
                >
                  <div class="chat-bubble__content">
                    <template v-for="(segment, index) in message.segments" :key="index">
                      <div v-if="segment.type === 'reply'" class="reply-segment">
                        <div class="reply-segment__head">
                          <div class="reply-segment__label">{{ t('chat.replyMessage') }}</div>
                          <button
                            class="reply-segment__jump"
                            type="button"
                            @click="scrollToMessage(segment.message_id)"
                          >
                            {{ t('chat.viewOriginalMessage') }}
                          </button>
                        </div>
                        <div v-if="segment.text" class="reply-segment__text">{{ segment.text }}</div>
                      </div>
                      <div v-else-if="segment.type === 'text'" class="text-body-2 chat-segment-text">
                        {{ segment.text }}
                      </div>
                      <v-chip
                        v-else-if="segment.type === 'mention'"
                        class="align-self-start"
                        color="secondary"
                        size="small"
                        variant="tonal"
                      >
                        @{{ segment.display || segment.target }}
                      </v-chip>
                      <img
                        v-else-if="segment.type === 'image' && resolveImageUrl(segment)"
                        :alt="segment.alt || t('chat.imageAlt')"
                        class="chat-image"
                        :src="resolveImageUrl(segment)"
                        @click="openImagePreview(segment)"
                      >
                      <pre v-else-if="segment.type === 'raw'" class="chat-raw">{{ JSON.stringify(segment.data, null, 2) }}</pre>
                    </template>
                  </div>

                  <div class="chat-bubble__actions">
                    <v-btn
                      prepend-icon="mdi-reply-outline"
                      size="x-small"
                      variant="text"
                      @click="startReplyToMessage(message)"
                    >
                      {{ t('chat.replyButton') }}
                    </v-btn>
                  </div>
                </v-card>
              </div>
            </div>
          </div>
        </div>

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
    ChatSegment,
    ImageSegment,
    MessageReceivePayload,
    SessionSnapshotPayload,
  } from '@/types/chat'
  import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import {
    buildComposerSegmentsFromRoot,
    createComposerImageNode,
    getComposerImageToken as findComposerImageToken,
    getOrderedComposerImages,
    type PendingImage,
    type PendingMention,
    readPendingImageFile,
    syncComposerImageTokenLabels as syncComposerImageLabels,
    syncComposerImageTokenState as syncComposerImageState,
  } from '@/views/chat/composer'
  import {
    estimateImageSize,
    formatBytes,
    useChatImagePreview,
  } from '@/views/chat/mediaPreview'
  import {
    createSessionKey,
    formatSessionTime,
    formatSessionTitle,
    getTextContent,
    hasImageSegment,
    summarizeReplyMessage,
  } from '@/views/chat/messageDisplay'
  import { useChatSessionState } from '@/views/chat/sessionState'
  import { useChatTransport } from '@/views/chat/transport'

  let composerRange: Range | null = null
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
  const messagesContainer = ref<HTMLElement>()
  const composerRef = ref<HTMLDivElement>()
  const imageInputRef = ref<HTMLInputElement>()
  const isPreparingImages = ref(false)
  const composerVersion = ref(0)
  const selectedComposerImageId = ref<string | null>(null)
  const reconnecting = transport.reconnecting
  const protectedAssetUrls = ref<Record<string, string>>({})
  const composerImages = new Map<string, PendingImage>()
  const composerMentions = new Map<string, PendingMention>()
  const loadingProtectedAssets = new Set<string>()
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

  const composerHasContent = computed(() => {
    const segments = buildComposerSegments()
    return segments.some(segment => {
      if (segment.type === 'text') {
        return segment.text.trim().length > 0
      }
      return true
    })
  })

  const orderedComposerImages = computed(() => {
    void composerVersion.value
    return getOrderedComposerImages(composerRef.value, composerImages)
  })

  function pickImages () {
    imageInputRef.value?.click()
  }

  async function handleImageSelection (event: Event) {
    const target = event.target as HTMLInputElement | null
    const files = Array.from(target?.files || [])
    if (files.length === 0) return

    isPreparingImages.value = true
    try {
      const images = await Promise.all(
        files.map(file => readPendingImageFile(file, t('chat.imageReadFailed'))),
      )
      for (const image of images) {
        composerImages.set(image.id, image)
        insertImageIntoComposer(image)
      }
    } finally {
      isPreparingImages.value = false
      if (target) {
        target.value = ''
      }
    }
  }

  async function ensureProtectedAssetUrl (rawUrl: string) {
    if (protectedAssetUrls.value[rawUrl] || loadingProtectedAssets.has(rawUrl)) return
    const token = localStorage.getItem('token')
    if (!token) return

    loadingProtectedAssets.add(rawUrl)
    try {
      const response = await fetch(rawUrl, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (!response.ok) {
        throw new Error(`Failed to load asset: ${response.status}`)
      }
      const blob = await response.blob()
      protectedAssetUrls.value = {
        ...protectedAssetUrls.value,
        [rawUrl]: URL.createObjectURL(blob),
      }
    } catch {
      protectedAssetUrls.value = { ...protectedAssetUrls.value }
    } finally {
      loadingProtectedAssets.delete(rawUrl)
    }
  }

  function revokeProtectedAssetUrls () {
    for (const url of Object.values(protectedAssetUrls.value)) {
      URL.revokeObjectURL(url)
    }
    protectedAssetUrls.value = {}
    loadingProtectedAssets.clear()
  }

  function resolveImageUrl (segment: ImageSegment) {
    if (segment.base64) {
      return `data:${segment.mime || 'image/png'};base64,${segment.base64}`
    }
    const rawUrl = segment.url
    if (!rawUrl) return ''
    if (!rawUrl.startsWith('/api/chat/assets/')) return rawUrl
    void ensureProtectedAssetUrl(rawUrl)
    return protectedAssetUrls.value[rawUrl] || ''
  }

  async function openImagePreview (segment: ImageSegment) {
    let src = resolveImageUrl(segment)
    if (!src && segment.url?.startsWith('/api/chat/assets/')) {
      await ensureProtectedAssetUrl(segment.url)
      src = protectedAssetUrls.value[segment.url] || ''
    }
    if (!src) return
    openImagePreviewSource(
      src,
      segment.alt || t('chat.imageAlt'),
      estimateImageSize(segment),
    )
  }

  function touchComposer () {
    composerVersion.value += 1
  }

  function captureComposerSelection () {
    const composer = composerRef.value
    if (!composer) return
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) return
    const range = selection.getRangeAt(0)
    if (!composer.contains(range.commonAncestorContainer)) return
    composerRange = range.cloneRange()
  }

  function focusComposer (placeAtEnd = false) {
    const composer = composerRef.value
    if (!composer) return
    composer.focus()
    const selection = window.getSelection()
    if (!selection) return

    let range = composerRange
    if (placeAtEnd || !range || !composer.contains(range.commonAncestorContainer)) {
      range = document.createRange()
      range.selectNodeContents(composer)
      range.collapse(false)
    }

    selection.removeAllRanges()
    selection.addRange(range)
    composerRange = range.cloneRange()
  }

  function insertTextAtCursor (text: string) {
    focusComposer()
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) return
    const range = selection.getRangeAt(0)
    range.deleteContents()
    const node = document.createTextNode(text)
    range.insertNode(node)
    range.setStartAfter(node)
    range.collapse(true)
    selection.removeAllRanges()
    selection.addRange(range)
    composerRange = range.cloneRange()
    touchComposer()
  }

  function getComposerImageToken (id: string) {
    return findComposerImageToken(composerRef.value, id)
  }

  function syncComposerImageTokenState () {
    syncComposerImageState(composerRef.value, selectedComposerImageId.value)
  }

  function selectComposerImage (id: string | null) {
    selectedComposerImageId.value = id
    syncComposerImageTokenState()
  }

  function insertImageIntoComposer (image: PendingImage) {
    focusComposer()
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) return
    const range = selection.getRangeAt(0)
    range.deleteContents()

    const token = createComposerImageNode(image, t('chat.imageToken'))
    const caretAnchor = document.createTextNode('')
    range.insertNode(caretAnchor)
    range.insertNode(token)

    range.setStart(caretAnchor, 0)
    range.collapse(true)
    selection.removeAllRanges()
    selection.addRange(range)
    composerRange = range.cloneRange()
    syncComposerImageTokenLabels()
    selectComposerImage(image.id)
    touchComposer()
  }

  function removeComposerImage (id: string) {
    const composer = composerRef.value
    if (!composer) return
    const node = composer.querySelector<HTMLElement>(`[data-image-id="${id}"]`)
    node?.remove()
    composerImages.delete(id)
    if (selectedComposerImageId.value === id) {
      selectComposerImage(null)
    }
    focusComposer(true)
    syncComposerImageTokenLabels()
    touchComposer()
  }

  function removeComposerMention (id: string) {
    const composer = composerRef.value
    if (!composer) return
    const node = composer.querySelector<HTMLElement>(`[data-kind="mention-token"][data-mention-id="${id}"]`)
    node?.remove()
    composerMentions.delete(id)
    focusComposer(true)
    touchComposer()
  }

  function placeCaretAroundToken (node: HTMLElement, direction: 'before' | 'after') {
    const selection = window.getSelection()
    if (!selection) return
    const range = document.createRange()
    if (direction === 'before') {
      range.setStartBefore(node)
    } else {
      range.setStartAfter(node)
    }
    range.collapse(true)
    selection.removeAllRanges()
    selection.addRange(range)
    composerRange = range.cloneRange()
  }

  function moveComposerImageToCursor (id: string) {
    const token = getComposerImageToken(id)
    if (!token) return
    focusComposer()
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) return
    const range = selection.getRangeAt(0)
    if (token.contains(range.commonAncestorContainer)) {
      return
    }
    token.remove()
    range.deleteContents()
    const caretAnchor = document.createTextNode('')
    range.insertNode(caretAnchor)
    range.insertNode(token)
    range.setStart(caretAnchor, 0)
    range.collapse(true)
    selection.removeAllRanges()
    selection.addRange(range)
    composerRange = range.cloneRange()
    syncComposerImageTokenLabels()
    selectComposerImage(id)
    touchComposer()
  }

  function handleComposerInput () {
    syncComposerImageTokenLabels()
    syncComposerImageTokenState()
    touchComposer()
    captureComposerSelection()
  }

  function handleComposerKeydown (event: KeyboardEvent) {
    if (!chatReady.value && event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      return
    }
    const selectedId = selectedComposerImageId.value
    if (selectedId) {
      const token = getComposerImageToken(selectedId)
      if (token) {
        if (event.key === 'Backspace' || event.key === 'Delete') {
          event.preventDefault()
          removeComposerImage(selectedId)
          return
        }
        if (event.key === 'ArrowLeft') {
          event.preventDefault()
          selectComposerImage(null)
          placeCaretAroundToken(token, 'before')
          return
        }
        if (event.key === 'ArrowRight') {
          event.preventDefault()
          selectComposerImage(null)
          placeCaretAroundToken(token, 'after')
          return
        }
      }
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send()
    }
  }

  function handleComposerClick (event: MouseEvent) {
    const target = event.target as HTMLElement | null
    if (!target) return
    const removeButton = target.closest<HTMLElement>('[data-action="remove-image"]')
    if (removeButton?.dataset.imageId) {
      event.preventDefault()
      removeComposerImage(removeButton.dataset.imageId)
      return
    }
    const removeMentionButton = target.closest<HTMLElement>('[data-action="remove-mention"]')
    if (removeMentionButton?.dataset.mentionId) {
      event.preventDefault()
      removeComposerMention(removeMentionButton.dataset.mentionId)
      return
    }
    const imageToken = target.closest<HTMLElement>('[data-kind="image-token"][data-image-id]')
    if (imageToken?.dataset.imageId) {
      event.preventDefault()
      selectComposerImage(imageToken.dataset.imageId)
      return
    }
    const mentionToken = target.closest<HTMLElement>('[data-kind="mention-token"][data-mention-id]')
    if (mentionToken) {
      event.preventDefault()
      return
    }
    selectComposerImage(null)
    captureComposerSelection()
  }

  function handleComposerPaste (event: ClipboardEvent) {
    event.preventDefault()
    const text = event.clipboardData?.getData('text/plain') || ''
    if (text) {
      insertTextAtCursor(text)
    }
  }

  function syncComposerImageTokenLabels () {
    syncComposerImageLabels(
      composerRef.value,
      index => t('chat.imageIndexedToken', { index: index + 1 }),
    )
  }

  function buildComposerSegments (): ChatSegment[] {
    void composerVersion.value
    return buildComposerSegmentsFromRoot(
      composerRef.value,
      composerImages,
      composerMentions,
    )
  }

  function clearComposer () {
    const composer = composerRef.value
    if (composer) {
      composer.innerHTML = ''
    }
    for (const image of composerImages.values()) {
      URL.revokeObjectURL(image.previewUrl)
    }
    composerImages.clear()
    composerMentions.clear()
    composerRange = null
    selectComposerImage(null)
    touchComposer()
  }

  function openImagePreviewFromPending (image: PendingImage) {
    openImagePreviewSource(image.previewUrl, image.name, formatBytes(image.size))
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
      client.sendMessage({
        session_id: session.value.session_id,
        message_id: messageId,
        segments,
      })
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
    const container = messagesContainer.value
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
      messagesContainer.value?.scrollTo({
        top: messagesContainer.value.scrollHeight,
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

.chat-panel__messages {
  min-height: 0;
  overflow: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: rgb(var(--v-theme-surface));
}

.chat-panel__composer {
  border-top: 1px solid rgba(var(--v-theme-outline-variant), 0.72);
  background: rgb(var(--v-theme-surface-container-low));
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-empty {
  margin: auto;
  max-width: 420px;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.chat-empty__title {
  font-size: 1.1rem;
  font-weight: 700;
}

.chat-message-row {
  display: flex;
  width: 100%;
}

.chat-message {
  width: 100%;
  border-radius: var(--shape-base);
  transition:
    background-color var(--motion-base) var(--motion-ease),
    box-shadow var(--motion-base) var(--motion-ease);
}

.chat-message--flash {
  background: rgba(var(--v-theme-secondary), 0.08);
  box-shadow: 0 0 0 1px rgba(var(--v-theme-secondary), 0.14);
}

.chat-message-row--user {
  justify-content: flex-end;
}

.chat-message-row--bot {
  justify-content: flex-start;
}

.chat-message-row--system {
  justify-content: center;
}

.chat-message-stack {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-width: min(78%, 760px);
}

.chat-message-stack--user {
  align-items: flex-end;
}

.chat-message-stack--bot {
  align-items: flex-start;
}

.chat-bubble {
  padding: 11px 13px 7px;
  border-radius: var(--shape-medium) !important;
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 2px 8px rgba(15, 23, 42, 0.05);
}

.chat-bubble--image {
  max-width: min(78vw, 720px);
}

.chat-bubble--user {
  border-top-right-radius: 8px !important;
  color: rgb(var(--v-theme-on-primary-container));
  background: rgb(var(--v-theme-primary-container)) !important;
}

.chat-bubble--bot {
  border-top-left-radius: 8px !important;
  background: rgb(var(--v-theme-surface-container)) !important;
}

.chat-bubble--error {
  border-top-left-radius: 8px !important;
}

.chat-bubble__content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-bubble__actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}

:deep(.chat-bubble--user .v-btn) {
  color: rgba(var(--v-theme-on-primary-container), 0.82);
}

:deep(.chat-bubble__actions .v-btn) {
  min-width: 0;
  padding-inline: 2px;
  font-size: 0.72rem;
  opacity: 0.48;
  letter-spacing: 0;
}

:deep(.chat-bubble__actions .v-btn .v-btn__prepend) {
  margin-inline-end: 2px;
}

:deep(.chat-bubble__actions .v-btn:hover) {
  opacity: 0.9;
}

.chat-segment-text {
  white-space: pre-wrap;
}

.chat-raw {
  white-space: pre-wrap;
  margin: 0;
  font-size: 0.85rem;
}

.chat-image {
  display: block;
  width: auto;
  max-width: 100%;
  max-height: min(52vh, 560px);
  border-radius: var(--shape-medium);
  cursor: zoom-in;
}

.reply-segment {
  padding: 8px 10px;
  border-radius: var(--shape-small);
  border-left: 2px solid rgba(var(--v-theme-secondary), 0.4);
  background: rgba(var(--v-theme-on-surface), 0.045);
}

.chat-bubble--user .reply-segment {
  border-left-color: rgba(var(--v-theme-primary), 0.42);
  background: rgba(255, 255, 255, 0.26);
}

.chat-bubble--bot .reply-segment,
.chat-bubble--error .reply-segment {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.reply-segment__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 2px;
}

.reply-segment__label {
  font-size: 0.7rem;
  font-weight: 700;
  opacity: 0.72;
}

.reply-segment__text {
  font-size: 0.76rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.chat-bubble--user .reply-segment__label,
.chat-bubble--user .reply-segment__text {
  color: rgba(var(--v-theme-on-primary-container), 0.84);
}

.chat-bubble--bot .reply-segment__label,
.chat-bubble--error .reply-segment__label {
  color: rgba(var(--v-theme-on-surface), 0.88);
}

.chat-bubble--bot .reply-segment__text,
.chat-bubble--error .reply-segment__text {
  color: rgba(var(--v-theme-on-surface), 0.72);
}

.reply-segment__jump {
  border: 0;
  padding: 0;
  background: transparent;
  color: rgba(var(--v-theme-primary), 0.82);
  font-size: 0.7rem;
  cursor: pointer;
  opacity: 0.68;
}

.chat-bubble--user .reply-segment__jump {
  color: rgba(var(--v-theme-on-primary-container), 0.76);
}

.chat-bubble--bot .reply-segment__jump,
.chat-bubble--error .reply-segment__jump {
  color: rgba(var(--v-theme-primary), 0.82);
}

.reply-segment__jump:hover {
  text-decoration: underline;
  opacity: 1;
}

.reply-segment__jump:focus-visible {
  outline: none;
  text-decoration: underline;
  opacity: 1;
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
