export type FeedbackEmptyCause = 'no-data' | 'filtered' | 'selection-required' | 'pending'
export type FeedbackLoadPhase = 'idle' | 'initial' | 'refreshing'
export type FeedbackTaskTone = 'default' | 'success' | 'warning' | 'error' | 'info'

export interface CollectionFeedbackInput {
  errorMessage?: string
  hasFilters?: boolean
  loading: boolean
  totalCount: number
  visibleCount: number
}

export interface CollectionFeedbackState {
  ariaBusy: boolean
  canRetry: boolean
  emptyCause: FeedbackEmptyCause | ''
  hasError: boolean
  isInitialLoading: boolean
  isRefreshing: boolean
  showEmpty: boolean
  showStaleError: boolean
}

const ACTIVE_TASK_STATUSES = new Set(['pending', 'queued', 'running'])

export function resolveCollectionFeedback(
  input: CollectionFeedbackInput,
): CollectionFeedbackState {
  const hasVisibleItems = input.visibleCount > 0
  const hasAnyItems = input.totalCount > 0
  const hasError = Boolean(input.errorMessage?.trim())
  const isInitialLoading = input.loading && !hasAnyItems
  const isRefreshing = input.loading && hasAnyItems
  const showEmpty = !input.loading && !hasVisibleItems && !hasError

  return {
    ariaBusy: input.loading,
    canRetry: hasError,
    emptyCause: showEmpty
      ? input.hasFilters
        ? 'filtered'
        : 'no-data'
      : '',
    hasError,
    isInitialLoading,
    isRefreshing,
    showEmpty,
    showStaleError: hasError && hasAnyItems,
  }
}

export function hasActiveFeedbackFilters(values: readonly unknown[]): boolean {
  return values.some(value => {
    if (typeof value === 'string') {
      return value.trim().length > 0
    }
    if (Array.isArray(value)) {
      return value.length > 0
    }
    return Boolean(value)
  })
}

export function isTaskActive(status: string | null | undefined): boolean {
  return ACTIVE_TASK_STATUSES.has(status || '')
}

export function isTaskTerminal(status: string | null | undefined): boolean {
  return status === 'succeeded' || status === 'failed'
}

export function taskStatusTone(status: string | null | undefined): FeedbackTaskTone {
  if (status === 'succeeded') {
    return 'success'
  }
  if (status === 'failed') {
    return 'error'
  }
  if (isTaskActive(status)) {
    return 'info'
  }
  return 'default'
}
