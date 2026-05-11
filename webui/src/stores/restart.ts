import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

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

const STORAGE_KEY = 'apeiria-restart-pending'

export const useRestartStore = defineStore('restart', () => {
  const entries = ref<RestartPendingEntry[]>(readEntries())

  const hasPendingRestart = computed(() => entries.value.length > 0)
  const pendingCount = computed(() => entries.value.length)

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

  return {
    entries,
    hasPendingRestart,
    pendingCount,
    markPending,
    clearPending,
  }
})

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
