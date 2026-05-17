import type { DirConfigItem, ModuleConfigItem } from '@/api/core'
import type { RestartPendingEntry } from '@/stores/restart'
import type { AdapterDraftDiagnostics, AdapterDraftRow, CoreTranslate } from '@/utils/adapterStatus'
import { computed, ref } from 'vue'
import { getPluginConfig, updatePluginConfig } from '@/api/core'
import { getErrorMessage } from '@/api/client'
import { buildAdapterDraftDiagnostics, normalizeAdapterModules } from '@/utils/adapterStatus'

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

interface RestartStoreLike {
  markPending: (entry: Omit<RestartPendingEntry, 'updated_at'>) => void
}

function normalizePluginDirs(values: string[]) {
  return Array.from(
    new Set(
      values
        .map(value => value.trim())
        .filter(Boolean),
    ),
  ).sort((left, right) => left.localeCompare(right))
}

export function usePluginLoadingRules(options: {
  noticeStore: NoticeStoreLike
  restartStore: RestartStoreLike
  t: CoreTranslate
}) {
  const loading = ref(false)
  const saving = ref(false)
  const errorMessage = ref('')
  const modules = ref<ModuleConfigItem[]>([])
  const dirs = ref<DirConfigItem[]>([])
  const moduleRows = ref<AdapterDraftRow[]>([])
  const dirRows = ref<AdapterDraftRow[]>([])
  const rowSeed = ref(0)

  const savedModules = computed(() => modules.value.map(item => item.name))
  const savedDirs = computed(() => dirs.value.map(item => item.path))
  const normalizedModules = computed(() =>
    normalizeAdapterModules(moduleRows.value.map(item => item.value)),
  )
  const normalizedDirs = computed(() =>
    normalizePluginDirs(dirRows.value.map(item => item.value)),
  )
  const hasPendingChanges = computed(() =>
    JSON.stringify(normalizedModules.value) !== JSON.stringify(savedModules.value)
    || JSON.stringify(normalizedDirs.value) !== JSON.stringify(savedDirs.value),
  )
  const moduleStatusByName = computed(() =>
    new Map(modules.value.map(item => [item.name, item] as const)),
  )
  const dirStatusByPath = computed(() =>
    new Map(dirs.value.map(item => [item.path, item] as const)),
  )
  const moduleDiagnostics = computed(() =>
    buildAdapterDraftDiagnostics(
      moduleRows.value.map(item => item.value),
      savedModules.value,
    ),
  )
  const dirDiagnostics = computed<AdapterDraftDiagnostics>(() =>
    buildAdapterDraftDiagnostics(
      dirRows.value.map(item => item.value),
      savedDirs.value,
    ),
  )
  const normalizationNotes = computed(() => {
    const notes: string[] = []
    if (moduleDiagnostics.value.blankRowCount > 0 || dirDiagnostics.value.blankRowCount > 0) {
      notes.push(options.t('plugins.configBlankRowsIgnored'))
    }
    if (moduleDiagnostics.value.duplicateModules.length > 0) {
      notes.push(options.t('plugins.configDuplicateModules', {
        modules: moduleDiagnostics.value.duplicateModules.join(', '),
      }))
    }
    if (dirDiagnostics.value.duplicateModules.length > 0) {
      notes.push(options.t('plugins.configDuplicateDirs', {
        dirs: dirDiagnostics.value.duplicateModules.join(', '),
      }))
    }
    if (hasPendingChanges.value) {
      notes.push(options.t('plugins.configDirDescription'))
    }
    return notes
  })
  const loadedModuleCount = computed(() =>
    modules.value.filter(item => item.is_loaded).length,
  )
  const availableDirCount = computed(() =>
    dirs.value.filter(item => item.exists).length,
  )

  function nextRowId(prefix: 'plugin-module' | 'plugin-dir') {
    const id = `${prefix}-${rowSeed.value}`
    rowSeed.value += 1
    return id
  }

  function setModuleRows(values: string[]) {
    moduleRows.value = values.map(value => ({
      id: nextRowId('plugin-module'),
      value,
    }))
  }

  function setDirRows(values: string[]) {
    dirRows.value = values.map(value => ({
      id: nextRowId('plugin-dir'),
      value,
    }))
  }

  function addModuleRow() {
    moduleRows.value.push({
      id: nextRowId('plugin-module'),
      value: '',
    })
  }

  function addDirRow() {
    dirRows.value.push({
      id: nextRowId('plugin-dir'),
      value: '',
    })
  }

  function removeModuleRow(rowId: string) {
    moduleRows.value = moduleRows.value.filter(item => item.id !== rowId)
  }

  function removeDirRow(rowId: string) {
    dirRows.value = dirRows.value.filter(item => item.id !== rowId)
  }

  function moduleStatusSummary(value: string) {
    const normalized = value.trim()
    if (!normalized) {
      return ''
    }
    const item = moduleStatusByName.value.get(normalized)
    if (!item) {
      return options.t('plugins.moduleRegisteredOnly')
    }
    if (item.is_loaded) {
      return options.t('plugins.moduleLoaded')
    }
    if (item.is_importable) {
      return options.t('plugins.moduleRegisteredOnly')
    }
    return options.t('plugins.moduleMissing')
  }

  function dirStatusSummary(value: string) {
    const normalized = value.trim()
    if (!normalized) {
      return ''
    }
    const item = dirStatusByPath.value.get(normalized)
    if (!item) {
      return options.t('plugins.dirRegisteredOnly')
    }
    if (!item.exists) {
      return options.t('plugins.dirMissing')
    }
    return item.is_loaded
      ? options.t('plugins.dirLoaded')
      : options.t('plugins.dirRegisteredOnly')
  }

  async function reload() {
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await getPluginConfig()
      modules.value = response.data.modules
      dirs.value = response.data.dirs
      setModuleRows(response.data.modules.map(item => item.name))
      setDirRows(response.data.dirs.map(item => item.path))
    } catch (error) {
      errorMessage.value = getErrorMessage(error, options.t('plugins.loadFailed'))
    } finally {
      loading.value = false
    }
  }

  async function save() {
    if (saving.value || !hasPendingChanges.value) {
      return false
    }
    saving.value = true
    errorMessage.value = ''
    const previousModules = [...savedModules.value]
    const previousDirs = [...savedDirs.value]
    try {
      const response = await updatePluginConfig({
        modules: normalizedModules.value,
        dirs: normalizedDirs.value,
      })
      modules.value = response.data.modules
      dirs.value = response.data.dirs
      setModuleRows(response.data.modules.map(item => item.name))
      setDirRows(response.data.dirs.map(item => item.path))
      options.restartStore.markPending({
        id: 'plugins:loading-rules',
        scope: 'plugins',
        summary: options.t('restart.pendingPluginLoadingRules'),
        undo: {
          kind: 'plugin-config',
          modules: previousModules,
          dirs: previousDirs,
        },
      })
      options.noticeStore.show(options.t('plugins.configSaved'), 'success')
      return true
    } catch (error) {
      const message = getErrorMessage(error, options.t('plugins.configSaveFailed'))
      errorMessage.value = message
      options.noticeStore.show(message, 'error')
      return false
    } finally {
      saving.value = false
    }
  }

  return {
    addDirRow,
    addModuleRow,
    availableDirCount,
    dirDiagnostics,
    dirRows,
    dirStatusSummary,
    dirs,
    errorMessage,
    hasPendingChanges,
    loadedModuleCount,
    loading,
    moduleDiagnostics,
    moduleRows,
    moduleStatusSummary,
    modules,
    normalizationNotes,
    reload,
    removeDirRow,
    removeModuleRow,
    save,
    saving,
  }
}
