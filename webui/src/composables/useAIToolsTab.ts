import type { AIToolExecutionItem, AIToolItem } from '@/api/ai'
import { ref } from 'vue'
import {
  getAIRecentToolExecutions,
  getAITools,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIToolsTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const tools = ref<AIToolItem[]>([])
  const executions = ref<AIToolExecutionItem[]>([])
  const loadingTools = ref(false)

  async function loadToolsData(limit = 20) {
    loadingTools.value = true
    try {
      const [toolsResponse, executionsResponse] = await Promise.all([
        getAITools(),
        getAIRecentToolExecutions({ limit }),
      ])
      tools.value = toolsResponse.data
      executions.value = executionsResponse.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.loadFailed')), 'error')
    } finally {
      loadingTools.value = false
    }
  }

  return {
    executions,
    loadToolsData,
    loadingTools,
    tools,
  }
}
