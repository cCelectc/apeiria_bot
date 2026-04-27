import type { AIFutureTaskItem } from '@/api/ai/types'
import { reactive, ref } from 'vue'
import { cancelAIFutureTask, getAIFutureTasks } from '@/api/ai/futureTasks'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIFutureTasksTab (t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const loadingFutureTasks = ref(false)
  const cancellingTaskId = ref('')
  const futureTasks = ref<AIFutureTaskItem[]>([])
  const futureTaskForm = reactive({
    limit: 20,
  })

  async function loadFutureTasks () {
    loadingFutureTasks.value = true
    try {
      const response = await getAIFutureTasks({ limit: futureTaskForm.limit })
      futureTasks.value = response.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.futureTaskLoadFailed')), 'error')
    } finally {
      loadingFutureTasks.value = false
    }
  }

  async function cancelFutureTask (taskId: string) {
    cancellingTaskId.value = taskId
    try {
      const response = await cancelAIFutureTask(taskId)
      const updatedTask = response.data
      if (updatedTask) {
        futureTasks.value = futureTasks.value.map(item => item.task_id === taskId ? updatedTask : item)
      }
      noticeStore.show(t('ai.futureTaskCancelled'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.futureTaskCancelFailed')), 'error')
    } finally {
      cancellingTaskId.value = ''
    }
  }

  return {
    cancelFutureTask,
    cancellingTaskId,
    futureTaskForm,
    futureTasks,
    loadFutureTasks,
    loadingFutureTasks,
  }
}
