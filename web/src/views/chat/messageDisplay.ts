import type {
  ChatSegment,
  MessageReceivePayload,
  SessionListItem,
} from '@/types/chat'

export type ChatTranslate = (
  key: string,
  params?: Record<string, unknown>,
) => string

export function getTextContent (
  segments: ChatSegment[],
  t: ChatTranslate,
) {
  return segments
    .map(segment => {
      if (segment.type === 'text') {
        return segment.text
      }
      if (segment.type === 'image') {
        return t('chat.imageToken')
      }
      if (segment.type === 'mention') {
        return `@${segment.display || segment.target}`
      }
      if (segment.type === 'reply') {
        return t('chat.replySummary', { messageId: segment.message_id })
      }
      return `[${segment.segment_type}]`
    })
    .join(' ')
}

export function hasImageSegment (segments: ChatSegment[]) {
  return segments.some(segment => segment.type === 'image')
}

export function summarizeReplyMessage (
  message: MessageReceivePayload,
  t: ChatTranslate,
) {
  const text = getTextContent(message.segments, t).trim()
  return text || t('chat.imageSummary')
}

export function formatSessionTitle (item: SessionListItem, t: ChatTranslate) {
  const sessionId = item.session.session_id
  const shortId = sessionId.slice(-4)
  return t('chat.sessionLabel', { id: shortId })
}

export function createSessionKey () {
  return `${Date.now()}`
}

export function formatSessionTime (value?: string | null) {
  if (!value) {
    return ''
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return date.toLocaleString()
}
