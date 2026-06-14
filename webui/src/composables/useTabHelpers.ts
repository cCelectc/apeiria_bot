import { ALL_FILTER } from '@/constants'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function optionalFilter(value: string) {
  return value === ALL_FILTER ? undefined : value
}

export function useTabErrorHandler(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  return function handleError(error: unknown, fallbackKey: string) {
    noticeStore.show(getErrorMessage(error, t(fallbackKey)), 'error')
  }
}
