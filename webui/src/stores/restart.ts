import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  filterPendingEntriesForRuntime,
  runtimeStartedAtFromUptime,
} from '@/utils/restartPendingState'

export type RestartUndoAction =
  | { kind: 'core-settings', values: Record<string, unknown> }
  | { kind: 'core-raw', text: string }
  | { kind: 'adapter-config', modules: string[] }
  | { kind: 'adapter-install', packageName: string, moduleName: string }
  | { kind: 'plugin-settings', moduleName: string, values: Record<string, unknown> }
  | { kind: 'plugin-raw', moduleName: string, text: string }
  | { kind: 'plugin-config', modules: string[], dirs: string[] }
  | { kind: 'plugin-toggle', moduleName: string, enabled: boolean }
  | { kind: 'plugin-install', packageName: string, moduleName: string }

export interface RestartPendingEntry {
  id: string
  scope: string
  summary: string
  undo?: RestartUndoAction
  updated_at: string
}

export type ReversibleRestartPendingEntry = RestartPendingEntry & {
  undo: RestartUndoAction
}

const STORAGE_KEY = 'apeiria-restart-pending'

export const useRestartStore = defineStore('restart', () => {
  const entries = ref<RestartPendingEntry[]>(readEntries())

  const hasPendingRestart = computed(() => entries.value.length > 0)
  const reversibleEntries = computed<ReversibleRestartPendingEntry[]>(() =>
    entries.value.filter(hasUndoAction),
  )
  const pendingCount = computed(() => entries.value.length)
  const reversibleCount = computed(() => reversibleEntries.value.length)
  const hasReversiblePending = computed(() => reversibleCount.value > 0)

  function markPending(entry: Omit<RestartPendingEntry, 'updated_at'>) {
    const nextEntry: RestartPendingEntry = {
      ...entry,
      updated_at: new Date().toISOString(),
    }
    const nextEntries = entries.value.filter(item => item.id !== entry.id)
    nextEntries.unshift(nextEntry)
    entries.value = nextEntries
    persistEntries(entries.value)
  }

  function clearPending(id?: string) {
    entries.value = id
      ? entries.value.filter(item => item.id !== id)
      : []
    persistEntries(entries.value)
  }

  function syncRuntimeUptime(uptimeSeconds: number | null | undefined) {
    const runtimeStartedAt = runtimeStartedAtFromUptime(uptimeSeconds)
    const nextEntries = filterPendingEntriesForRuntime(
      entries.value,
      runtimeStartedAt,
    )
    if (nextEntries.length === entries.value.length) {
      return
    }
    entries.value = nextEntries
    persistEntries(entries.value)
  }

  return {
    entries,
    hasReversiblePending,
    hasPendingRestart,
    pendingCount,
    reversibleCount,
    reversibleEntries,
    markPending,
    clearPending,
    syncRuntimeUptime,
  }
})

function hasUndoAction(
  entry: RestartPendingEntry,
): entry is ReversibleRestartPendingEntry {
  return Boolean(entry.undo)
}

function persistEntries(entries: RestartPendingEntry[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
}

function readEntries() {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return [] as RestartPendingEntry[]
  }
  try {
    const parsed = JSON.parse(raw) as RestartPendingEntry[]
    return Array.isArray(parsed)
      ? parsed.filter(item =>
          item
          && typeof item.id === 'string'
          && typeof item.scope === 'string'
          && typeof item.summary === 'string'
          && typeof item.updated_at === 'string',
        )
      : []
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return [] as RestartPendingEntry[]
  }
}
