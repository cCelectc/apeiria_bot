import type { ChatEnvelope } from '@/types/chat'
import { ref } from 'vue'
import { ChatClient } from '@/api/chat'

interface ChatTransportOptions {
  onClose: () => void
  onMessage: (event: ChatEnvelope) => void
  onOpen: (client: ChatClient) => void
}

export function useChatTransport(options: ChatTransportOptions) {
  const client = new ChatClient()
  const socketConnected = ref(false)
  const reconnecting = ref(false)
  let reconnectTimer: number | null = null
  let reconnectAttempts = 0
  let shouldReconnect = true

  function clearReconnectTimer() {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function scheduleReconnect() {
    if (!shouldReconnect || reconnectTimer !== null) {
      return
    }
    reconnecting.value = true
    const delay = Math.min(1000 * 2 ** reconnectAttempts, 5000)
    reconnectAttempts += 1
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  function connect() {
    clearReconnectTimer()
    if (client.isConnected()) {
      return
    }
    client.connect()
  }

  function reconnect() {
    reconnecting.value = true
    reconnectAttempts = 0
    clearReconnectTimer()
    client.disconnect()
    connect()
  }

  const unsubscribeMessage = client.onMessage(options.onMessage)
  const unsubscribeOpen = client.onOpen(() => {
    clearReconnectTimer()
    reconnectAttempts = 0
    reconnecting.value = false
    socketConnected.value = true
    options.onOpen(client)
  })
  const unsubscribeClose = client.onClose(() => {
    socketConnected.value = false
    options.onClose()
    scheduleReconnect()
  })

  function start() {
    shouldReconnect = true
    connect()
  }

  function stop() {
    shouldReconnect = false
    clearReconnectTimer()
    unsubscribeMessage()
    unsubscribeOpen()
    unsubscribeClose()
    client.disconnect()
  }

  return {
    client,
    reconnect,
    reconnecting,
    socketConnected,
    start,
    stop,
  }
}
