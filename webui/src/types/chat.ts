export type EnvelopeVersion = '1.0'
export type SessionStatus = 'ready' | 'closed' | 'error'
export type MessageRole = 'user' | 'bot' | 'system' | 'error'

export interface TextSegment {
  type: 'text'
  text: string
}

export interface ImageSegment {
  type: 'image'
  url?: string
  asset_id?: string
  base64?: string
  mime?: string
  alt?: string
  width?: number
  height?: number
}

export interface MentionSegment {
  type: 'mention'
  target: string
  display?: string
  mention_type: string
}

export interface ReplySegment {
  type: 'reply'
  message_id: string
  text?: string
}

export interface RawSegment {
  type: 'raw'
  segment_type: string
  data: Record<string, unknown>
}

export type ChatSegment =
  | TextSegment
  | ImageSegment
  | MentionSegment
  | ReplySegment
  | RawSegment

export interface WebUIPrincipal {
  id: string
  username: string
  role: string
}

export interface ChatSessionState {
  session_id: string
  status: SessionStatus
  target_user_id: string
  created_by?: WebUIPrincipal | null
  created_at?: string | null
  updated_at?: string | null
}

export interface SessionListItem {
  session: ChatSessionState
  message_count: number
  last_message?: string | null
  last_message_at?: string | null
}

export interface ChatCapabilities {
  segment_types: string[]
  mock_apis: string[]
}

export interface AuthHelloPayload {
  token: string
}

export interface AuthOkPayload {
  principal: WebUIPrincipal
}

export interface ErrorPayload {
  code: string
  message: string
}

export interface SessionCreatePayload {
  target_user_id: string
}

export interface SessionSelectPayload {
  session_id: string
}

export interface SessionDeletePayload {
  session_id: string
}

export interface SessionSnapshotPayload {
  active_session?: ChatSessionState | null
  sessions: SessionListItem[]
  history: MessageReceivePayload[]
}

export interface MessageSendPayload {
  session_id: string
  message_id: string
  segments: ChatSegment[]
}

export interface MessageAckPayload {
  session_id: string
  message_id: string
  accepted: boolean
}

export interface MessageReceivePayload {
  session_id: string
  message_id: string
  role: MessageRole
  segments: ChatSegment[]
  timestamp: string
  trace_id?: string | null
}

export interface PartialReplyStartPayload {
  session_id: string
  trace_id: string
  stream_id: string
}

export interface PartialReplyDeltaPayload {
  session_id: string
  trace_id: string
  stream_id: string
  content_delta: string
}

export interface PartialReplyCompletePayload {
  session_id: string
  trace_id: string
  stream_id: string
  message_id?: string | null
}

export interface PartialReplyFailedPayload {
  session_id: string
  trace_id: string
  stream_id: string
  code: string
  message?: string | null
}

export interface SystemMessagePayload {
  message: string
}

export interface CapabilitiesResponsePayload {
  capabilities: ChatCapabilities
}

export interface ChatEnvelope<T = unknown> {
  version: EnvelopeVersion
  type: string
  request_id?: string
  payload: T
}
