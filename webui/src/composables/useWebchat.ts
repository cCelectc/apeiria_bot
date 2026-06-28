import { onMounted, onUnmounted, ref } from "vue";
import { toast } from "vue-sonner";
import { createWsClient, type WsClient } from "@/lib/ws";
import { useAuthStore } from "@/stores/auth";
import type { WebchatIdentity, WebchatMessage, WebchatOutFrame } from "@/types";

export function useWebchat() {
  const auth = useAuthStore();
  const messages = ref<WebchatMessage[]>([]);
  const connected = ref(false);
  const identity = ref<WebchatIdentity>({ scene_type: "private" });
  let client: WsClient | null = null;

  function handleFrame(raw: string) {
    let frame: WebchatOutFrame;
    try {
      frame = JSON.parse(raw) as WebchatOutFrame;
    } catch {
      return;
    }
    switch (frame.type) {
      case "history":
        messages.value = frame.messages;
        break;
      case "message":
        messages.value = [...messages.value, frame.message];
        break;
      case "cleared":
        messages.value = [];
        break;
      case "deleted":
        messages.value = messages.value.filter(
          (m) => m.id !== frame.message_id,
        );
        break;
      case "error":
        toast.error(frame.message);
        break;
    }
  }

  function send(text: string, image?: string) {
    const trimmed = text.trim();
    if (!client || (!trimmed && !image)) return;
    client.send(
      JSON.stringify({
        type: "message",
        text: trimmed,
        image,
        identity: identity.value,
      }),
    );
  }

  function clear() {
    client?.send(JSON.stringify({ type: "clear" }));
  }

  function deleteMessage(id: string) {
    client?.send(JSON.stringify({ type: "delete", message_id: id }));
  }

  function setIdentity(next: WebchatIdentity) {
    identity.value = { ...identity.value, ...next };
  }

  onMounted(() => {
    if (!auth.token) return;
    client = createWsClient("/ws/webchat", auth.token, {
      onMessage: handleFrame,
      onOpen: () => (connected.value = true),
      onClose: () => (connected.value = false),
    });
  });

  onUnmounted(() => {
    client?.close();
    client = null;
  });

  return {
    messages,
    connected,
    identity,
    send,
    clear,
    deleteMessage,
    setIdentity,
  };
}
