import type { AIFutureTaskItem } from './types'

import client from '../client'

export function getAIFutureTasks (params?: {
  limit?: number
}) {
  return client.get<AIFutureTaskItem[]>('/ai/future-tasks', { params })
}

export function cancelAIFutureTask (taskId: string) {
  return client.delete<AIFutureTaskItem | null>('/ai/future-tasks', {
    params: { task_id: taskId },
  })
}
