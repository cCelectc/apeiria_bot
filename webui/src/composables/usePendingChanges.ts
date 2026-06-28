import { ref } from "vue";

const pendingChanges = ref(false);

export function usePendingChanges() {
  return {
    pendingChanges,
    markChanged: () => {
      pendingChanges.value = true;
    },
    clearChanges: () => {
      pendingChanges.value = false;
    },
  };
}
