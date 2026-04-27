import type { PluginItem } from '@/api/plugins'
import type { RawSettingsResponse } from '@/api/settings'
import type { RestartPendingEntry } from '@/stores/restart'
import type { PluginTranslate } from '@/views/plugins/display'
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
import {
  buildRevertValues,
  buildSettingsPreviewItems,
  type PluginSettingField,
} from '@/views/plugins/settingsEditor'
import { useSettingsEditor } from '@/views/plugins/useSettingsEditor'

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

interface RestartStoreLike {
  markPending: (entry: Omit<RestartPendingEntry, 'updated_at'>) => void
}

export function usePluginSettingsDialog (options: {
  noticeStore: NoticeStoreLike
  restartStore: RestartStoreLike
  t: PluginTranslate
}) {
  const settingsDialogVisible = ref(false)
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
        id: `plugin:settings:${settingsPlugin.value.module_name}`,
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

  const settingsDialogLoading = pluginEditor.loading
  const settingsSaving = pluginEditor.saving
  const settingsErrorMessage = pluginEditor.errorMessage
  const settingsState = pluginEditor.state
  const settingsFields = pluginEditor.fields
  const settingsForm = pluginEditor.form
  const hasPendingPluginChanges = pluginEditor.hasPendingChanges
  const hasPendingPluginRawChanges = computed(() => settingsRawText.value !== settingsRawInitialText.value)
  const previewSaving = computed(() => settingsSaving.value || settingsRawSaving.value)
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

  function applyPluginRawState (nextState: RawSettingsResponse) {
    settingsRawText.value = nextState.text
    settingsRawInitialText.value = nextState.text
  }

  async function loadPluginRawSettings (moduleName: string) {
    settingsRawLoading.value = true
    settingsRawErrorMessage.value = ''
    try {
      const response = await getPluginSettingsRaw(moduleName)
      applyPluginRawState(response.data)
    } catch (error) {
      settingsRawErrorMessage.value = getErrorMessage(
        error,
        options.t('plugins.settingsRawLoadFailed'),
      )
    } finally {
      settingsRawLoading.value = false
    }
  }

  async function openSettings (item: PluginItem) {
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
    try {
      const settingsResponse = await getPluginSettings(item.module_name)
      pluginEditor.applyState(settingsResponse.data)
    } catch (error) {
      settingsErrorMessage.value = getErrorMessage(
        error,
        options.t('plugins.settingsLoadFailed'),
      )
    } finally {
      settingsDialogLoading.value = false
      settingsLoadingModule.value = ''
    }
    await loadPluginRawSettings(item.module_name)
  }

  async function saveSettings () {
    if (!settingsPlugin.value || !settingsState.value) {
      return
    }
    await pluginEditor.submit()
  }

  async function clearPluginField (field: PluginSettingField) {
    pluginEditor.clearField(field)
  }

  function openPluginSettingsPreview () {
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

  async function savePluginRawSettings () {
    if (!settingsPlugin.value || !hasPendingPluginRawChanges.value) {
      return
    }
    settingsRawSaving.value = true
    settingsRawErrorMessage.value = ''
    const previousText = settingsRawInitialText.value
    try {
      const rawResponse = await updatePluginSettingsRaw(settingsPlugin.value.module_name, {
        text: settingsRawText.value,
      })
      const settingsResponse = await getPluginSettings(settingsPlugin.value.module_name)
      applyPluginRawState(rawResponse.data)
      pluginEditor.applyState(settingsResponse.data)
      options.restartStore.markPending({
        id: `plugin:raw:${settingsPlugin.value.module_name}`,
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

  async function openPluginRawPreview () {
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

  async function confirmPreviewSave () {
    await (previewAction.value === 'plugin-basic'
      ? saveSettings()
      : savePluginRawSettings())

    if (!settingsErrorMessage.value && !settingsRawErrorMessage.value) {
      previewDialogVisible.value = false
    }
  }

  return {
    clearPluginField,
    confirmPreviewSave,
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
  }
}
