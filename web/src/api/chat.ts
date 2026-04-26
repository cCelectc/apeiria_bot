import type {
  AuthHelloPayload,
  ChatEnvelope,
  MessageSendPayload,
  SessionCreatePayload,
  SessionDeletePayload,
  SessionSelectPayload,
} from '@/types/chat'

type EnvelopeHandler = (event: ChatEnvelope) => void
type VoidHandler = () => void

function makeRequestId (prefix: string) {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}_${crypto.randomUUID()}`
  }
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

export class ChatClient {
  private ws: WebSocket | null = null
  private messageHandlers = new Set<EnvelopeHandler>()
  private openHandlers = new Set<VoidHandler>()
  private closeHandlers = new Set<VoidHandler>()

  connect () {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.ws = new WebSocket(`${proto}//${location.host}/api/chat/ws`)

    this.ws.addEventListener('open', () => {
      for (const handler of this.openHandlers) {
        handler()
      }
    })

    this.ws.addEventListener('close', () => {
      for (const handler of this.closeHandlers) {
        handler()
      }
    })

    this.ws.addEventListener('message', event => {
      try {
        const parsed = JSON.parse(event.data) as ChatEnvelope
        for (const handler of this.messageHandlers) {
          handler(parsed)
        }
      } catch {
        for (const handler of this.messageHandlers) {
          handler({
            version: '1.0',
            type: 'system.error',
            payload: { code: 'INVALID_FRAME', message: String(event.data) },
          })
        }
      }
    })
  }

  disconnect () {
    this.ws?.close()
    this.ws = null
  }

  isConnected () {
    return this.ws?.readyState === WebSocket.OPEN
  }

  onMessage (handler: EnvelopeHandler) {
    this.messageHandlers.add(handler)
    return () => this.messageHandlers.delete(handler)
  }

  onOpen (handler: VoidHandler) {
    this.openHandlers.add(handler)
    return () => this.openHandlers.delete(handler)
  }

  onClose (handler: VoidHandler) {
    this.closeHandlers.add(handler)
    return () => this.closeHandlers.delete(handler)
  }

  send<T>(type: string, payload: T, requestId = makeRequestId(type.replace('.', '_'))) {
    this.ws?.send(JSON.stringify({
      version: '1.0',
      type,
      request_id: requestId,
      payload,
    }))
    return requestId
  }

  authenticate (token: string) {
    const payload: AuthHelloPayload = { token }
    return this.send('auth.hello', payload)
  }

  requestCapabilities () {
    return this.send('capabilities.request', {})
  }

  createSession (payload: SessionCreatePayload) {
    return this.send('session.create', payload)
  }

  selectSession (payload: SessionSelectPayload) {
    return this.send('session.select', payload)
  }

  sendMessage (payload: MessageSendPayload) {
    return this.send('message.send', payload)
  }

  closeSession () {
    return this.send('session.close', {})
  }

  clearHistory () {
    return this.send('session.clear_history', {})
  }

  listSessions () {
    return this.send('session.list', {})
  }

  deleteSession (payload: SessionDeletePayload) {
    return this.send('session.delete', payload)
  }
}
