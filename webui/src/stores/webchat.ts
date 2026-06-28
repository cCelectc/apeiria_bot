import { defineStore } from "pinia";
import { ref } from "vue";
import type { WebchatSimGroup, WebchatSimUser } from "@/types";

export const useWebchatStore = defineStore(
  "webchat",
  () => {
    const users = ref<WebchatSimUser[]>([]);
    const groups = ref<WebchatSimGroup[]>([]);
    const currentUserId = ref("");
    const currentConversationKey = ref("");

    function ensureUser(id: string, name?: string) {
      if (!id) return;
      if (!users.value.some((u) => u.id === id)) {
        users.value = [...users.value, { id, name: name || id }];
      }
    }

    function removeUser(id: string) {
      users.value = users.value.filter((u) => u.id !== id);
      if (currentUserId.value === id) {
        currentUserId.value = users.value[0]?.id ?? "";
      }
    }

    function setCurrentUser(id: string) {
      currentUserId.value = id;
    }

    function addGroup(id: string, name?: string) {
      if (!id) return;
      if (!groups.value.some((g) => g.id === id)) {
        groups.value = [...groups.value, { id, name: name || id }];
      }
    }

    function removeGroup(id: string) {
      groups.value = groups.value.filter((g) => g.id !== id);
    }

    function setCurrentConversation(key: string) {
      currentConversationKey.value = key;
    }

    function userName(id: string): string {
      return users.value.find((u) => u.id === id)?.name ?? id;
    }

    return {
      users,
      groups,
      currentUserId,
      currentConversationKey,
      ensureUser,
      removeUser,
      setCurrentUser,
      addGroup,
      removeGroup,
      setCurrentConversation,
      userName,
    };
  },
  { persist: true },
);
