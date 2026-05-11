import { defineStore } from 'pinia'
import { ref } from 'vue'

export type NoticeTone = 'success' | 'error' | 'warning' | 'info'

export const useNoticeStore = defineStore('notice', () => {
  const visible = ref(false)
  const message = ref('')
  const color = ref<NoticeTone>('info')

  function show(nextMessage: string, nextColor: NoticeTone = 'info') {
    message.value = nextMessage
    color.value = nextColor
    visible.value = true
  }

  function hide() {
    visible.value = false
  }

  return { visible, message, color, show, hide }
})
