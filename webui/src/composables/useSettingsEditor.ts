import type { SettingsResponse } from '@/api/settings'
import type { SettingsState, SettingField } from '@/utils/settingsEditor'
import { computed, ref } from 'vue'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'
import {
  buildClearedFieldValue,
  buildFieldFormValue,
  buildPendingSettingsFields,
  buildSettingsForm,
  buildSettingsUpdate,
  hasFieldPendingChange,
  hasPendingChanges,
} from '@/utils/settingsEditor'

interface SettingsEditorMessages {
  invalidJson: string
  loadFailed: string
  saveFailed: string
  saveSuccess: string
}

interface SettingsEditorResponse {
  data: SettingsResponse
}

interface UseSettingsEditorOptions {
  afterSave?: (context: {
    previousState: SettingsState
    values: Record<string, unknown>
    clear: string[]
  }) => void
  load?: () => Promise<SettingsEditorResponse>
  messages: SettingsEditorMessages
  save: (payload: {
    values: Record<string, unknown>
    clear: string[]
  }) => Promise<SettingsEditorResponse>
}

export function useSettingsEditor(options: UseSettingsEditorOptions) {
  const noticeStore = useNoticeStore()
  const loading = ref(false)
  const saving = ref(false)
  const errorMessage = ref('')
  const state = ref<SettingsState | null>(null)
  const form = ref<Record<string, unknown>>({})
  const draftClears = ref<Record<string, boolean>>({})

  const fields = computed(() =>
    [...(state.value?.fields ?? [])]
      .sort((left, right) => {
        if (left.order !== right.order) {
          return left.order - right.order
        }
        return left.key.localeCompare(right.key)
      }),
  )
  const hasPendingChangesState = computed(() =>
    hasPendingChanges(
      buildPendingSettingsFields(fields.value),
      form.value,
      draftClears.value,
      options.messages.invalidJson,
    ),
  )

  function applyState(nextState: SettingsState) {
    state.value = nextState
    form.value = buildSettingsForm(nextState.fields)
    draftClears.value = {}
  }

  function reset() {
    state.value = null
    form.value = {}
    draftClears.value = {}
    errorMessage.value = ''
  }

  function hasFieldPending(field: SettingField) {
    return hasFieldPendingChange(
      field,
      form.value,
      draftClears.value,
      options.messages.invalidJson,
    )
  }

  async function reload() {
    if (!options.load) {
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await options.load()
      applyState(response.data)
    } catch (error) {
      errorMessage.value = getErrorMessage(error, options.messages.loadFailed)
    } finally {
      loading.value = false
    }
  }

  async function submit() {
    const editingFields = buildPendingSettingsFields(fields.value)
    let payload: { values: Record<string, unknown>, clear: string[] }
    try {
      payload = buildSettingsUpdate(
        editingFields,
        form.value,
        draftClears.value,
        options.messages.invalidJson,
      )
    } catch (error) {
      const message = getErrorMessage(error, options.messages.invalidJson)
      errorMessage.value = message
      noticeStore.show(message, 'error')
      return false
    }

    if (Object.keys(payload.values).length === 0 && payload.clear.length === 0) {
      return false
    }

    saving.value = true
    errorMessage.value = ''
    try {
      const response = await options.save(payload)
      const previousState = state.value
      applyState(response.data)
      if (previousState) {
        options.afterSave?.({
          previousState,
          values: payload.values,
          clear: payload.clear,
        })
      }
      noticeStore.show(options.messages.saveSuccess, 'success')
      return true
    } catch (error) {
      const message = getErrorMessage(error, options.messages.saveFailed)
      errorMessage.value = message
      noticeStore.show(message, 'error')
      return false
    } finally {
      saving.value = false
    }
  }

  function clearField(field: SettingField) {
    draftClears.value = {
      ...draftClears.value,
      [field.key]: true,
    }
    form.value[field.key] = buildClearedFieldValue(field)
    errorMessage.value = ''
  }

  function cancelField(field: SettingField) {
    const nextDraftClears = { ...draftClears.value }
    delete nextDraftClears[field.key]
    draftClears.value = nextDraftClears
    form.value[field.key] = buildFieldFormValue(field)
    errorMessage.value = ''
  }

  function updateFieldValue(field: SettingField, value: unknown) {
    const nextDraftClears = { ...draftClears.value }
    delete nextDraftClears[field.key]
    draftClears.value = nextDraftClears
    form.value[field.key] = value
    errorMessage.value = ''
  }

  return {
    applyState,
    cancelField,
    clearField,
    draftClears,
    errorMessage,
    fields,
    form,
    hasFieldPending,
    hasPendingChanges: hasPendingChangesState,
    loading,
    reload,
    reset,
    saving,
    state,
    submit,
    updateFieldValue,
  }
}
