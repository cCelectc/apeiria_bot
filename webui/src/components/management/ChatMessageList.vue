<script setup lang="ts">
import type { ImageSegment, MessageReceivePayload } from '@/types/chat'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  getTextContent,
  hasImageSegment,
} from '@/utils/chatDisplay'

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

<template>
  <div ref="rootRef" class="chat-panel__messages">
    <div v-if="messages.length === 0" class="chat-empty">
      <div class="chat-empty__title">{{ t('chat.newSession') }}</div>
      <p>{{ t('chat.noMessages') }}</p>
    </div>

    <article
      v-for="message in messages"
      :key="`${message.message_id}-${message.timestamp}`"
      class="chat-message"
      :data-message-id="message.message_id"
    >
      <div
        v-if="message.role === 'system'"
        class="chat-message-row chat-message-row--system"
      >
        <Badge variant="secondary">{{ getTextContent(message.segments, t) }}</Badge>
      </div>

      <div
        v-else-if="message.role === 'error'"
        class="chat-message-row chat-message-row--bot"
      >
        <div class="chat-message-stack chat-message-stack--bot">
          <div class="chat-bubble chat-bubble--error">
            <template v-for="(segment, index) in message.segments" :key="index">
              <div v-if="segment.type === 'text'" class="chat-segment-text">
                {{ segment.text }}
              </div>
            </template>
          </div>
        </div>
      </div>

      <div
        v-else
        class="chat-message-row"
        :class="message.role === 'user'
          ? 'chat-message-row--user'
          : 'chat-message-row--bot'"
      >
        <div
          class="chat-message-stack"
          :class="message.role === 'user'
            ? 'chat-message-stack--user'
            : 'chat-message-stack--bot'"
        >
          <div
            class="chat-bubble"
            :class="{
              'chat-bubble--bot': message.role === 'bot',
              'chat-bubble--image': hasImageSegment(message.segments),
              'chat-bubble--user': message.role === 'user',
            }"
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
                  <div v-if="segment.text" class="reply-segment__text">
                    {{ segment.text }}
                  </div>
                </div>
                <div v-else-if="segment.type === 'text'" class="chat-segment-text">
                  {{ segment.text }}
                </div>
                <Badge
                  v-else-if="segment.type === 'mention'"
                  class="chat-mention"
                  variant="secondary"
                >
                  @{{ segment.display || segment.target }}
                </Badge>
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
              <Button size="sm" variant="ghost" @click="$emit('reply', message)">
                {{ t('chat.replyButton') }}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </article>
  </div>
</template>
