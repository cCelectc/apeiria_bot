import type { AdapterConfigItem } from '@/api/adapters'
import type { RestartPendingEntry } from '@/stores/restart'
import type { AdapterDraftRow, CoreTranslate } from '@/views/core/adapterStatus'
import { computed, ref } from 'vue'
import { getAdapterConfig, updateAdapterConfig } from '@/api/adapters'
import { getErrorMessage } from '@/api/client'
import {
  adapterStatusSummary,
  buildAdapterDraftDiagnostics,
  normalizeAdapterModules,
} from '@/views/core/adapterStatus'

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

interface RestartStoreLike {
  markPending: (entry: Omit<RestartPendingEntry, 'updated_at'>) => void
}

export function useAdapterManagement (options: {
  noticeStore: NoticeStoreLike
  restartStore: RestartStoreLike
  t: CoreTranslate
}) {
  const loading = ref(false)
  const saving = ref(false)
  const errorMessage = ref('')
  const adapterModules = ref<AdapterConfigItem[]>([])
  const draftRows = ref<AdapterDraftRow[]>([])
  const rowSeed = ref(0)

  const savedModules = computed(() => adapterModules.value.map(item => item.name))
  const normalizedDraft = computed(() => normalizeAdapterModules(
    draftRows.value.map(item => item.value),
  ))
  const hasPendingChanges = computed(() => {
    return JSON.stringify(normalizedDraft.value) !== JSON.stringify(savedModules.value)
  })
  const statusByName = computed(() => new Map(
    adapterModules.value.map(item => [item.name, item] as const),
  ))
  const configuredModules = computed(() => adapterModules.value)
  const adapterCount = computed(() => adapterModules.value.length)
  const diagnostics = computed(() => buildAdapterDraftDiagnostics(
    draftRows.value.map(item => item.value),
    savedModules.value,
  ))
  const blankRowCount = computed(() => diagnostics.value.blankRowCount)
  const duplicateModules = computed(() => diagnostics.value.duplicateModules)
  const addedModules = computed(() => diagnostics.value.addedModules)
  const removedModules = computed(() => diagnostics.value.removedModules)
  const unchangedModules = computed(() => diagnostics.value.unchangedModules)
  const normalizationNotes = computed(() => {
    const notes: string[] = []
    if (blankRowCount.value > 0) {
      notes.push(options.t('core.adapterIgnoredBlankRows', { count: blankRowCount.value }))
    }
    if (duplicateModules.value.length > 0) {
      notes.push(options.t('core.adapterDuplicateRows', { modules: duplicateModules.value.join(', ') }))
    }
    if (hasPendingChanges.value) {
      notes.push(options.t('core.adapterRestartRequired'))
    }
    return notes
  })
  const previewItems = computed(() => [
    {
      key: options.t('core.adapterPreviewCurrent'),
      value: savedModules.value,
    },
    {
      key: options.t('core.adapterPreviewNext'),
      value: normalizedDraft.value,
    },
    {
      key: options.t('core.adapterPreviewAdded'),
      value: addedModules.value,
    },
    {
      key: options.t('core.adapterPreviewRemoved'),
      value: removedModules.value,
    },
  ])

  function setDraftRows (modules: string[]) {
    draftRows.value = modules.map(value => ({
      id: nextRowId(),
      value,
    }))
  }

  function nextRowId () {
    const id = `adapter-module-${rowSeed.value}`
    rowSeed.value += 1
    return id
  }

  function addDraftRow () {
    draftRows.value.push({
      id: nextRowId(),
      value: '',
    })
  }

  function removeDraftRow (rowId: string) {
    draftRows.value = draftRows.value.filter(item => item.id !== rowId)
  }

  function rowStatusSummary (value: string) {
    const normalized = value.trim()
    if (!normalized) {
      return ''
    }
    return adapterStatusSummary(statusByName.value.get(normalized), options.t)
  }

  function rowState (value: string) {
    const normalized = value.trim()
    return normalized ? statusByName.value.get(normalized) : undefined
  }

  async function reload () {
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await getAdapterConfig()
      adapterModules.value = response.data.modules
      setDraftRows(response.data.modules.map(item => item.name))
    } catch (error) {
      errorMessage.value = getErrorMessage(error, options.t('core.adapterLoadFailed'))
    } finally {
      loading.value = false
    }
  }

  async function save () {
    if (saving.value || !hasPendingChanges.value) {
      return false
    }
    saving.value = true
    errorMessage.value = ''
    const previousModules = [...savedModules.value]
    try {
      const response = await updateAdapterConfig({
        modules: normalizedDraft.value,
      })
      adapterModules.value = response.data.modules
      setDraftRows(response.data.modules.map(item => item.name))
      options.restartStore.markPending({
        id: 'core:adapter-config',
        scope: 'core',
        summary: options.t('restart.pendingAdapterConfig'),
        undo: {
          kind: 'adapter-config',
          modules: previousModules,
        },
      })
      options.noticeStore.show(options.t('core.adapterSaved'), 'success')
      return true
    } catch (error) {
      const message = getErrorMessage(error, options.t('core.adapterSaveFailed'))
      errorMessage.value = message
      options.noticeStore.show(message, 'error')
      return false
    } finally {
      saving.value = false
    }
  }

  return {
    addDraftRow,
    addedModules,
    adapterCount,
    blankRowCount,
    configuredModules,
    diagnostics,
    duplicateModules,
    draftRows,
    errorMessage,
    hasPendingChanges,
    loading,
    normalizationNotes,
    previewItems,
    reload,
    removeDraftRow,
    removedModules,
    rowState,
    rowStatusSummary,
    save,
    saving,
    unchangedModules,
  }
}
