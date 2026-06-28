import { computed, onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { toast } from "vue-sonner";
import { createWsClient, type WsClient } from "@/lib/ws";
import { useAuthStore } from "@/stores/auth";
import { useWebchatStore } from "@/stores/webchat";
import type {
  WebchatConversation,
  WebchatIdentity,
  WebchatInFrame,
  WebchatMessage,
  WebchatOutFrame,
} from "@/types";

const PRIVATE_PREFIX = "webchat:private:";

function privateKey(userId: string): string {
  return `webchat:private:${userId}`;
}

function groupKey(groupId: string): string {
  return `webchat:group:${groupId}`;
}

export function useWebchat() {
  const auth = useAuthStore();
  const store = useWebchatStore();
  const { t } = useI18n();

  const connected = ref(false);
  const messagesBySession = ref<Record<string, WebchatMessage[]>>({});
  let client: WsClient | null = null;

  const conversations = computed<WebchatConversation[]>(() => {
    const uid = store.currentUserId;
    if (!uid) return [];
    const list: WebchatConversation[] = [
      { key: privateKey(uid), type: "private", name: t("webchat.privateChat") },
    ];
    for (const g of store.groups) {
      list.push({
        key: groupKey(g.id),
        type: "group",
        name: g.name,
        groupId: g.id,
      });
    }
    return list;
  });

  const currentConversation = computed<WebchatConversation | undefined>(() =>
    conversations.value.find((c) => c.key === store.currentConversationKey),
  );

  const activeMessages = computed<WebchatMessage[]>(
    () => messagesBySession.value[store.currentConversationKey] ?? [],
  );

  function identityFor(conv: WebchatConversation): WebchatIdentity {
    if (conv.type === "group") {
      return {
        user_id: store.currentUserId,
        scene_type: "group",
        scene_id: conv.groupId,
      };
    }
    return { user_id: store.currentUserId, scene_type: "private" };
  }

  function sendFrame(frame: WebchatInFrame) {
    client?.send(JSON.stringify(frame));
  }

  function handleFrame(raw: string) {
    let frame: WebchatOutFrame;
    try {
      frame = JSON.parse(raw) as WebchatOutFrame;
    } catch {
      return;
    }
    switch (frame.type) {
      case "history":
        messagesBySession.value = {
          ...messagesBySession.value,
          [frame.session_id]: frame.messages,
        };
        if (
          !store.currentUserId &&
          frame.session_id.startsWith(PRIVATE_PREFIX)
        ) {
          const uid = frame.session_id.slice(PRIVATE_PREFIX.length);
          store.ensureUser(uid);
          store.setCurrentUser(uid);
          store.setCurrentConversation(frame.session_id);
        }
        break;
      case "message": {
        const sid = frame.message.session_id;
        messagesBySession.value = {
          ...messagesBySession.value,
          [sid]: [...(messagesBySession.value[sid] ?? []), frame.message],
        };
        break;
      }
      case "cleared":
        messagesBySession.value = {
          ...messagesBySession.value,
          [frame.session_id]: [],
        };
        break;
      case "deleted": {
        const next: Record<string, WebchatMessage[]> = {};
        for (const [k, arr] of Object.entries(messagesBySession.value)) {
          next[k] = arr.filter((m) => m.id !== frame.message_id);
        }
        messagesBySession.value = next;
        break;
      }
      case "error":
        toast.error(frame.message);
        break;
    }
  }

  function selectConversation(conv: WebchatConversation) {
    store.setCurrentConversation(conv.key);
    sendFrame({ type: "switch", identity: identityFor(conv) });
  }

  function switchUser(id: string) {
    if (!id) return;
    store.setCurrentUser(id);
    selectConversation({
      key: privateKey(id),
      type: "private",
      name: t("webchat.privateChat"),
    });
  }

  function addUser(id: string, name?: string) {
    const trimmed = id.trim();
    if (!trimmed) return;
    store.ensureUser(trimmed, name?.trim() || undefined);
    switchUser(trimmed);
  }

  function removeUser(id: string) {
    store.removeUser(id);
    if (store.currentUserId) switchUser(store.currentUserId);
  }

  function addGroup(id: string, name?: string) {
    const trimmed = id.trim();
    if (!trimmed) return;
    const label = name?.trim() || trimmed;
    store.addGroup(trimmed, label);
    selectConversation({
      key: groupKey(trimmed),
      type: "group",
      name: label,
      groupId: trimmed,
    });
  }

  function removeGroup(id: string) {
    store.removeGroup(id);
    if (store.currentConversationKey === groupKey(id)) {
      switchUser(store.currentUserId);
    }
  }

  function send(text: string, image?: string) {
    const conv = currentConversation.value;
    const trimmed = text.trim();
    if (!conv || (!trimmed && !image)) return;
    sendFrame({
      type: "message",
      text: trimmed,
      identity: identityFor(conv),
      ...(image ? { image } : {}),
    });
  }

  function clear() {
    sendFrame({ type: "clear" });
  }

  function deleteMessage(id: string) {
    sendFrame({ type: "delete", message_id: id });
  }

  onMounted(() => {
    if (!auth.token) return;
    client = createWsClient("/ws/webchat", auth.token, {
      onMessage: handleFrame,
      onOpen: () => {
        connected.value = true;
        const conv = currentConversation.value;
        if (conv) sendFrame({ type: "switch", identity: identityFor(conv) });
      },
      onClose: () => (connected.value = false),
    });
  });

  onUnmounted(() => {
    client?.close();
    client = null;
  });

  return {
    store,
    connected,
    conversations,
    currentConversation,
    activeMessages,
    send,
    clear,
    deleteMessage,
    selectConversation,
    switchUser,
    addUser,
    removeUser,
    addGroup,
    removeGroup,
  };
}
