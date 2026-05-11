import type { PluginItem } from '@/api/plugins'
import type { RestartPendingEntry } from '@/stores/restart'
import { computed, ref } from 'vue'
import { getErrorMessage } from '@/api/client'
import {
  getPluginSettings,
  getPluginSettingsRaw,
  updatePluginSettings,
  updatePluginSettingsRaw,
  validatePluginSettingsRaw,
} from '@/api/plugins'
import { useRawTomlValidation } from '@/composables/useRawTomlValidation'
import type { PluginTranslate } from '@/utils/pluginDisplay'
import {
  buildRevertValues,
  buildSettingsPreviewItems,
  cloneSettingValue,
  displayChoiceTitle,
  displayFieldValue,
  isNullableBoolField,
  isSequenceChipField,
  textInputType,
  type SettingField,
} from '@/utils/settingsEditor'
import { useSettingsEditor } from '@/composables/useSettingsEditor'

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

interface RestartStoreLike {
  markPending: (entry: Omit<RestartPendingEntry, 'updated_at'>) => void
}

interface FieldChoiceOption {
  key: string
  title: string
  value: unknown
}

export function usePluginSettingsDialog(options: {
  noticeStore: NoticeStoreLike
  restartStore: RestartStoreLike
  t: PluginTranslate
}) {
  const settingsDialogVisible = ref(false)
  const settingsDialogLoading = ref(false)
  const settingsLoadingModule = ref('')
  const settingsPlugin = ref<PluginItem | null>(null)
  const settingsEditorMode = ref<'basic' | 'advanced'>('basic')
  const settingsRawText = ref('')
  const settingsRawInitialText = ref('')
  const settingsRawLoading = ref(false)
  const settingsRawSaving = ref(false)
  const settingsRawErrorMessage = ref('')
  const previewDialogVisible = ref(false)
  const previewMode = ref<'basic' | 'raw'>('basic')
  const previewAction = ref<'plugin-basic' | 'plugin-raw'>('plugin-basic')

  const pluginEditor = useSettingsEditor({
    save: payload => updatePluginSettings(settingsPlugin.value!.module_name, payload),
    messages: {
      invalidJson: options.t('plugins.settingsInvalidJson'),
      loadFailed: options.t('plugins.settingsLoadFailed'),
      saveFailed: options.t('plugins.settingsSaveFailed'),
      saveSuccess: options.t('plugins.settingsSaved'),
    },
    afterSave: ({ previousState, values, clear }) => {
      if (!settingsPlugin.value) {
        return
      }
      options.restartStore.markPending({
        id: `plugin-settings:${settingsPlugin.value.module_name}`,
        scope: 'plugins',
        summary: options.t('restart.pendingPluginSettings', {
          name: settingsPlugin.value.name || settingsPlugin.value.module_name,
        }),
        undo: {
          kind: 'plugin-settings',
          moduleName: settingsPlugin.value.module_name,
          values: buildRevertValues(previousState.fields, values, clear),
        },
      })
    },
  })

  const settingsState = pluginEditor.state
  const settingsFields = pluginEditor.fields
  const settingsForm = pluginEditor.form
  const settingsSaving = pluginEditor.saving
  const settingsErrorMessage = pluginEditor.errorMessage
  const hasPendingPluginChanges = pluginEditor.hasPendingChanges
  const hasPendingPluginRawChanges = computed(
    () => settingsRawText.value !== settingsRawInitialText.value,
  )
  const previewSaving = computed(() =>
    settingsSaving.value || settingsRawSaving.value,
  )
  const previewTitle = computed(() =>
    previewMode.value === 'basic'
      ? options.t('plugins.previewChangesTitle')
      : options.t('plugins.previewRawTitle'),
  )
  const previewCurrentText = computed(() => settingsRawInitialText.value)
  const previewNextText = computed(() => settingsRawText.value)
  const previewItems = computed(() =>
    buildSettingsPreviewItems(
      settingsFields.value,
      settingsForm.value,
      pluginEditor.draftOverrides.value,
      pluginEditor.draftClears.value,
      options.t('plugins.settingsInvalidJson'),
    ),
  )
  const {
    validateNow: validatePluginRawNow,
    validationColumn: pluginRawValidationColumn,
    validationLine: pluginRawValidationLine,
    validationMessage: pluginRawValidationMessage,
    validationPending: pluginRawValidationPending,
  } = useRawTomlValidation({
    text: settingsRawText,
    initialText: settingsRawInitialText,
    fallbackMessage: options.t('plugins.settingsRawValidateFailed'),
    validate: async text => {
      if (!settingsPlugin.value) {
        return { valid: true, message: null, line: null, column: null }
      }
      return (await validatePluginSettingsRaw(settingsPlugin.value.module_name, { text })).data
    },
  })

  function applyPluginRawState(nextState: { text: string }) {
    settingsRawText.value = nextState.text
    settingsRawInitialText.value = nextState.text
  }

  function fieldSourceLabel(source: string) {
    const map: Record<string, string> = {
      default: options.t('plugins.settingsValueSourceDefault'),
      plugin_section: options.t('plugins.settingsValueSourcePlugin'),
      env: options.t('plugins.settingsValueSourceEnv'),
    }
    return map[source] || source
  }

  function formatFieldChoices(field: SettingField) {
    const normalized = field.choices
      .map(choice => displayChoiceTitle(choice))
      .filter(Boolean)
    if (normalized.length <= 4) {
      return normalized.join(' / ')
    }
    return `${normalized.slice(0, 4).join(' / ')} +${normalized.length - 4}`
  }

  function buildNullableBoolOptions(field: SettingField): FieldChoiceOption[] {
    return [
      { key: `${field.key}:nullable:null`, title: 'null', value: null },
      { key: `${field.key}:nullable:true`, title: 'true', value: true },
      { key: `${field.key}:nullable:false`, title: 'false', value: false },
    ]
  }

  function fieldChoiceOptions(field: SettingField): FieldChoiceOption[] {
    if (field.choices.length > 0) {
      return field.choices.map((choice, index) => ({
        key: `${field.key}:choice:${index}`,
        title: displayChoiceTitle(choice),
        value: choice.value,
      }))
    }
    return isNullableBoolField(field) ? buildNullableBoolOptions(field) : []
  }

  function selectedFieldChoiceKey(field: SettingField) {
    const options = fieldChoiceOptions(field)
    const value = settingsForm.value[field.key]
    const option = options.find(item =>
      JSON.stringify(item.value) === JSON.stringify(value),
    )
    return option?.key
  }

  function updateFieldChoice(field: SettingField, key: string | number) {
    const option = fieldChoiceOptions(field).find(item => item.key === String(key))
    if (option) {
      settingsForm.value[field.key] = cloneSettingValue(option.value)
    }
  }

  async function loadPluginRawSettings(moduleName: string) {
    settingsRawLoading.value = true
    settingsRawErrorMessage.value = ''
    try {
      const response = await getPluginSettingsRaw(moduleName)
      if (settingsPlugin.value?.module_name === moduleName) {
        applyPluginRawState(response.data)
      }
    } catch (error) {
      if (settingsPlugin.value?.module_name === moduleName) {
        settingsRawErrorMessage.value = getErrorMessage(
          error,
          options.t('plugins.settingsRawLoadFailed'),
        )
      }
    } finally {
      if (settingsPlugin.value?.module_name === moduleName) {
        settingsRawLoading.value = false
      }
    }
  }

  async function openSettings(item: PluginItem) {
    if (!item.can_edit_config) {
      return
    }
    settingsPlugin.value = item
    settingsDialogVisible.value = true
    settingsEditorMode.value = 'basic'
    settingsDialogLoading.value = true
    settingsLoadingModule.value = item.module_name
    pluginEditor.reset()
    settingsRawText.value = ''
    settingsRawInitialText.value = ''
    settingsRawErrorMessage.value = ''
    settingsRawLoading.value = true

    const [settingsResult, rawResult] = await Promise.allSettled([
      getPluginSettings(item.module_name),
      getPluginSettingsRaw(item.module_name),
    ])

    if (settingsPlugin.value?.module_name === item.module_name) {
      if (settingsResult.status === 'fulfilled') {
        pluginEditor.applyState(settingsResult.value.data)
      } else {
        pluginEditor.errorMessage.value = getErrorMessage(
          settingsResult.reason,
          options.t('plugins.settingsLoadFailed'),
        )
      }

      if (rawResult.status === 'fulfilled') {
        applyPluginRawState(rawResult.value.data)
      } else {
        settingsRawErrorMessage.value = getErrorMessage(
          rawResult.reason,
          options.t('plugins.settingsRawLoadFailed'),
        )
      }

      settingsDialogLoading.value = false
      settingsLoadingModule.value = ''
      settingsRawLoading.value = false
    }
  }

  async function savePluginRawSettings() {
    if (!settingsPlugin.value || !hasPendingPluginRawChanges.value) {
      return
    }
    settingsRawSaving.value = true
    settingsRawErrorMessage.value = ''
    const previousText = settingsRawInitialText.value
    try {
      const rawResponse = await updatePluginSettingsRaw(
        settingsPlugin.value.module_name,
        {
          text: settingsRawText.value,
        },
      )
      const settingsResponse = await getPluginSettings(settingsPlugin.value.module_name)
      applyPluginRawState(rawResponse.data)
      pluginEditor.applyState(settingsResponse.data)
      options.restartStore.markPending({
        id: `plugin-raw:${settingsPlugin.value.module_name}`,
        scope: 'plugins',
        summary: options.t('restart.pendingPluginRaw', {
          name: settingsPlugin.value.name || settingsPlugin.value.module_name,
        }),
        undo: {
          kind: 'plugin-raw',
          moduleName: settingsPlugin.value.module_name,
          text: previousText,
        },
      })
      options.noticeStore.show(options.t('plugins.settingsRawSaved'), 'success')
    } catch (error) {
      const message = getErrorMessage(error, options.t('plugins.settingsRawSaveFailed'))
      settingsRawErrorMessage.value = message
      options.noticeStore.show(message, 'error')
    } finally {
      settingsRawSaving.value = false
    }
  }

  async function openPluginSettingsPreview() {
    if (!settingsState.value) {
      return
    }
    const items = previewItems.value
    if (items.length === 0) {
      return
    }
    previewMode.value = 'basic'
    previewAction.value = 'plugin-basic'
    previewDialogVisible.value = true
  }

  async function openPluginRawPreview() {
    if (!hasPendingPluginRawChanges.value) {
      return
    }
    if (!await validatePluginRawNow()) {
      return
    }
    previewMode.value = 'raw'
    previewAction.value = 'plugin-raw'
    previewDialogVisible.value = true
  }

  async function confirmPreviewSave() {
    await (previewAction.value === 'plugin-basic'
      ? pluginEditor.submit()
      : savePluginRawSettings())

    if (!settingsErrorMessage.value && !settingsRawErrorMessage.value) {
      previewDialogVisible.value = false
    }
  }

  function clearPluginField(field: SettingField) {
    pluginEditor.clearField(field)
  }

  function closeSettingsDialog() {
    settingsDialogVisible.value = false
    settingsDialogLoading.value = false
    settingsLoadingModule.value = ''
    settingsPlugin.value = null
    settingsEditorMode.value = 'basic'
  }

  return {
    applyPluginRawState,
    clearPluginField,
    closeSettingsDialog,
    confirmPreviewSave,
    fieldChoiceOptions,
    fieldSourceLabel,
    formatFieldChoices,
    hasPendingPluginChanges,
    hasPendingPluginRawChanges,
    loadPluginRawSettings,
    openPluginRawPreview,
    openPluginSettingsPreview,
    openSettings,
    pluginEditor,
    pluginRawValidationColumn,
    pluginRawValidationLine,
    pluginRawValidationMessage,
    pluginRawValidationPending,
    previewCurrentText,
    previewDialogVisible,
    previewItems,
    previewMode,
    previewNextText,
    previewSaving,
    previewTitle,
    selectedFieldChoiceKey,
    settingsDialogLoading,
    settingsDialogVisible,
    settingsEditorMode,
    settingsErrorMessage,
    settingsFields,
    settingsForm,
    settingsLoadingModule,
    settingsPlugin,
    settingsRawErrorMessage,
    settingsRawInitialText,
    settingsRawLoading,
    settingsRawSaving,
    settingsRawText,
    settingsSaving,
    settingsState,
    updateFieldChoice,
    validatePluginRawNow,
    isNullableBoolField,
    isSequenceChipField,
    textInputType,
    displayFieldValue,
    displayChoiceTitle,
  }
}
