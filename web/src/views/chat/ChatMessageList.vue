<template>
  <div ref="rootRef" class="chat-panel__messages">
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
                      @click="$emit('scroll-to-message', segment.message_id)"
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
                  @click="$emit('open-image-preview', segment)"
                >
                <pre v-else-if="segment.type === 'raw'" class="chat-raw">{{ JSON.stringify(segment.data, null, 2) }}</pre>
              </template>
            </div>

            <div class="chat-bubble__actions">
              <v-btn
                prepend-icon="mdi-reply-outline"
                size="x-small"
                variant="text"
                @click="$emit('reply', message)"
              >
                {{ t('chat.replyButton') }}
              </v-btn>
            </div>
          </v-card>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import type { ImageSegment, MessageReceivePayload } from '@/types/chat'
  import { ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import {
    getTextContent,
    hasImageSegment,
  } from '@/views/chat/messageDisplay'

  defineProps<{
    messages: MessageReceivePayload[]
    resolveImageUrl: (segment: ImageSegment) => string
  }>()

  defineEmits<{
    'open-image-preview': [segment: ImageSegment]
    'reply': [message: MessageReceivePayload]
    'scroll-to-message': [messageId: string]
  }>()

  const { t } = useI18n()
  const rootRef = ref<HTMLElement>()

  defineExpose({
    getElement: () => rootRef.value || null,
  })
</script>

<style scoped>
.chat-panel__messages {
  min-height: 0;
  overflow: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: rgb(var(--v-theme-surface));
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
</style>
