import { defineStore } from "pinia"
import { ref } from "vue"

export type NoticeType = "success" | "error" | "warning" | "info"

interface Notice {
  message: string
  type: NoticeType
}

export const useNoticeStore = defineStore("notice", () => {
  const current = ref<Notice | null>(null)
  const pendingRestart = ref(false)

  function show(message: string, type: NoticeType = "info") {
    current.value = { message, type }
  }

  function hide() {
    current.value = null
  }

  function markRestartPending() {
    pendingRestart.value = true
  }

  function clearRestartPending() {
    pendingRestart.value = false
  }

  return {
    current,
    pendingRestart,
    show,
    hide,
    markRestartPending,
    clearRestartPending,
  }
})
