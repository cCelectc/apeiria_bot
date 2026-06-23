import { ref } from "vue"
import type { ChatEnvelope } from "@/types/chat"

let nextId = 0

export function useChatTransport() {
  const socket = ref<WebSocket | null>(null)
  const connected = ref(false)
  const listeners = new Map<string, Set<(payload: unknown) => void>>()

  function connect(url: string) {
    disconnect()
    const ws = new WebSocket(url)
    socket.value = ws

    ws.onopen = () => { connected.value = true }
    ws.onclose = () => { connected.value = false }
    ws.onmessage = (e) => {
      try {
        const env: ChatEnvelope = JSON.parse(e.data)
        const handlers = listeners.get(env.type)
        if (handlers) {
          for (const fn of handlers) fn(env.payload)
        }
      } catch { /* ignore */ }
    }
    ws.onerror = () => {}
  }

  function disconnect() {
    if (socket.value) {
      socket.value.close()
      socket.value = null
    }
    connected.value = false
  }

  function send(type: string, payload: unknown) {
    if (!socket.value || socket.value.readyState !== WebSocket.OPEN) return
    const env: ChatEnvelope = {
      version: "1.0",
      type,
      request_id: String(++nextId),
      payload,
    }
    socket.value.send(JSON.stringify(env))
    return env.request_id
  }

  function on(type: string, handler: (payload: unknown) => void) {
    if (!listeners.has(type)) listeners.set(type, new Set())
    listeners.get(type)!.add(handler)
    return () => { listeners.get(type)?.delete(handler) }
  }

  return { socket, connected, connect, disconnect, send, on }
}
