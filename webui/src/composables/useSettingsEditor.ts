import type { SettingsResponse } from '@/api/settings'
import type { SettingsState, SettingField } from '@/utils/settingsEditor'
import { computed, ref } from 'vue'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'
import {
  buildClearedFieldValue,
  buildFieldFormValue,
  buildOverrideInitialValue,
  buildSettingsForm,
  buildSettingsUpdate,
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
  const draftOverrides = ref<Record<string, boolean>>({})
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
      fields.value.filter(field => isFieldEditing(field)),
      form.value,
      draftClears.value,
      options.messages.invalidJson,
    ),
  )

  function applyState(nextState: SettingsState) {
    state.value = nextState
    form.value = buildSettingsForm(nextState.fields)
    draftOverrides.value = {}
    draftClears.value = {}
  }

  function reset() {
    state.value = null
    form.value = {}
    draftOverrides.value = {}
    draftClears.value = {}
    errorMessage.value = ''
  }

  function isFieldEditing(field: SettingField) {
    return (
      field.has_local_override
      || Boolean(draftOverrides.value[field.key])
      || Boolean(draftClears.value[field.key])
    )
  }

  function startOverride(field: SettingField) {
    const nextDraftClears = { ...draftClears.value }
    delete nextDraftClears[field.key]
    draftClears.value = nextDraftClears
    draftOverrides.value = {
      ...draftOverrides.value,
      [field.key]: true,
    }
    form.value[field.key] = buildOverrideInitialValue(field)
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
    const editingFields = fields.value.filter(field => isFieldEditing(field))
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
    const nextDraftOverrides = { ...draftOverrides.value }
    delete nextDraftOverrides[field.key]
    draftOverrides.value = nextDraftOverrides
    draftClears.value = {
      ...draftClears.value,
      [field.key]: true,
    }
    form.value[field.key] = buildClearedFieldValue(field)
    errorMessage.value = ''
  }

  function cancelField(field: SettingField) {
    const nextDraftOverrides = { ...draftOverrides.value }
    delete nextDraftOverrides[field.key]
    draftOverrides.value = nextDraftOverrides
    const nextDraftClears = { ...draftClears.value }
    delete nextDraftClears[field.key]
    draftClears.value = nextDraftClears
    form.value[field.key] = buildFieldFormValue(field)
    errorMessage.value = ''
  }

  return {
    applyState,
    cancelField,
    clearField,
    draftClears,
    draftOverrides,
    errorMessage,
    fields,
    form,
    hasPendingChanges: hasPendingChangesState,
    isFieldEditing,
    loading,
    reload,
    reset,
    saving,
    startOverride,
    state,
    submit,
  }
}
