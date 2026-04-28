<template>
  <div class="page-view">
    <div class="page-header">
      <h1 class="page-title">{{ t('core.title') }}</h1>
      <div class="page-actions">
        <v-btn :loading="loading" variant="tonal" @click="handleRefresh">{{ t('common.refresh') }}</v-btn>
      </div>
    </div>

    <v-alert v-if="errorMessage" density="comfortable" type="error" variant="tonal">
      {{ errorMessage }}
    </v-alert>

    <v-card class="page-panel">
      <v-tabs v-model="sectionTab" color="primary">
        <v-tab value="core">{{ t('core.coreTab') }}</v-tab>
        <v-tab value="adapters">{{ t('core.adaptersTab') }}</v-tab>
        <v-tab value="drivers">{{ t('core.driversTab') }}</v-tab>
      </v-tabs>

      <v-divider />

      <v-window v-model="sectionTab">
        <v-window-item value="core">
          <v-card-text class="d-flex flex-column ga-3">
            <div class="settings-shell">
              <div class="settings-shell__toolbar">
                <div class="settings-shell__headline">
                  <div class="text-subtitle-1 font-weight-medium">{{ t('core.coreTab') }}</div>
                </div>
              </div>

              <SettingsModeBar
                v-model="coreEditorMode"
                :advanced-label="t('plugins.settingsAdvancedTab')"
                :basic-label="t('plugins.settingsBasicTab')"
                :tablist-label="t('core.coreTab')"
              >
                <template #actions>
                  <v-btn
                    v-if="coreEditorMode === 'basic'"
                    color="primary"
                    :disabled="!hasPendingCoreChanges"
                    :loading="coreSaving"
                    @click="openCoreSettingsPreview"
                  >
                    {{ t('plugins.settingsSave') }}
                  </v-btn>
                </template>
              </SettingsModeBar>

              <template v-if="coreEditorMode === 'basic'">
                <v-alert v-if="coreErrorMessage" density="comfortable" type="error" variant="tonal">
                  {{ coreErrorMessage }}
                </v-alert>

                <v-progress-linear v-if="coreLoading" color="primary" indeterminate />

                <div v-else class="settings-list-panel">
                  <section
                    v-for="field in coreFields"
                    :key="field.key"
                    class="settings-list-row"
                  >
                    <div class="settings-list-row__main">
                      <div class="settings-list-row__info">
                        <div class="settings-list-row__label text-subtitle-2 font-weight-medium">
                          {{ field.label || field.key }}
                        </div>
                        <div v-if="field.help" class="settings-list-row__description text-caption text-medium-emphasis">
                          {{ field.help }}
                        </div>
                        <div class="settings-list-row__status">
                          <v-chip
                            v-if="field.has_local_override || coreEditor.isFieldEditing(field)"
                            color="primary"
                            size="x-small"
                            variant="tonal"
                          >
                            {{ t('plugins.settingsLocalShort') }}
                          </v-chip>
                          <v-chip
                            v-if="!field.editable"
                            color="warning"
                            size="x-small"
                            variant="tonal"
                          >
                            {{ t('plugins.settingsReadonly') }}
                          </v-chip>
                        </div>
                        <div class="settings-list-row__meta text-caption text-medium-emphasis">
                          <span>{{ t('plugins.settingsType') }}: {{ field.type }}</span>
                          <span>{{ t('plugins.settingsValueSource') }}: {{ settingsValueSourceLabel(field.value_source) }}</span>
                          <span v-if="field.global_key">{{ t('plugins.settingsGlobalKey') }}: {{ field.global_key }}</span>
                          <span v-if="field.choices.length > 0">{{ t('plugins.settingsChoices') }}: {{ formatFieldChoices(field.choices) }}</span>
                          <span>{{ t('plugins.settingsCurrent') }}: {{ displayFieldValue(field.current_value) }}</span>
                          <span v-if="field.has_local_override">{{ t('plugins.settingsLocal') }}: {{ displayFieldValue(field.local_value) }}</span>
                        </div>
                      </div>

                      <div class="settings-list-row__control">
                        <div class="settings-list-row__actions">
                          <v-btn
                            v-if="!coreEditor.isFieldEditing(field) && field.editable"
                            class="settings-action settings-action--primary"
                            color="primary"
                            size="small"
                            variant="tonal"
                            @click="coreEditor.startOverride(field)"
                          >
                            {{ t('plugins.settingsAddOverride') }}
                          </v-btn>
                          <v-btn
                            v-if="coreEditor.isFieldEditing(field)"
                            class="settings-action"
                            size="small"
                            variant="text"
                            @click="coreEditor.cancelField(field)"
                          >
                            {{ t('common.cancel') }}
                          </v-btn>
                          <v-btn
                            v-if="field.has_local_override"
                            class="settings-action"
                            color="warning"
                            size="small"
                            variant="text"
                            @click="clearCoreField(field)"
                          >
                            {{ t('plugins.settingsClear') }}
                          </v-btn>
                        </div>

                        <SettingsFieldEditor
                          v-model="coreForm[field.key]"
                          :array-hint="t('plugins.settingsArrayHint')"
                          :editing="coreEditor.isFieldEditing(field)"
                          :field="field"
                          :json-hint="t('plugins.settingsJsonHint')"
                        />
                      </div>
                    </div>
                  </section>
                </div>
              </template>

              <template v-else>
                <RawSettingsEditor
                  v-model="coreRawText"
                  :description="t('plugins.settingsAdvancedDescription')"
                  :dirty="hasPendingCoreRawChanges"
                  :error-message="coreRawErrorMessage"
                  :loading="coreRawLoading"
                  :reload-label="t('common.refresh')"
                  :save-label="t('plugins.settingsSave')"
                  :saving="coreRawSaving"
                  :validation-error-column="coreRawValidationColumn"
                  :validation-error-line="coreRawValidationLine"
                  :validation-error-message="coreRawValidationMessage"
                  :validation-pending="coreRawValidationPending"
                  @reload="loadCoreRawSettings"
                  @save="openCoreRawPreview"
                />
              </template>
            </div>
          </v-card-text>
        </v-window-item>

        <v-window-item value="adapters">
          <v-card-text class="d-flex flex-column ga-5">
            <AdapterManagementPanel ref="adapterManagementPanel" />
          </v-card-text>
        </v-window-item>

        <v-window-item value="drivers">
          <v-card-text class="d-flex flex-column ga-5">
            <div class="d-flex justify-space-between align-center flex-wrap ga-3">
              <div class="text-subtitle-1 font-weight-medium">{{ t('core.driversTab') }}</div>
              <v-sheet class="summary-card" rounded="lg">
                <div class="summary-card__label">{{ t('plugins.driverCount') }}</div>
                <div class="summary-card__value">{{ driverBuiltin.length }}</div>
              </v-sheet>
            </div>
            <div class="config-chip-row">
              <v-chip
                v-for="driverItem in driverBuiltin"
                :key="driverItem.name"
                :color="driverChipColor(driverItem)"
                variant="tonal"
              >
                {{ driverItem.name }}
                <v-tooltip activator="parent" location="top">
                  {{ driverStatusText(driverItem) }}
                </v-tooltip>
              </v-chip>
              <span v-if="driverBuiltin.length === 0" class="text-body-2 text-medium-emphasis">
                {{ t('plugins.emptyDriverBuiltin') }}
              </span>
            </div>
          </v-card-text>
        </v-window-item>
      </v-window>
    </v-card>

    <SettingsPreviewDialog
      v-model="previewDialogVisible"
      :cancel-label="t('common.cancel')"
      :confirm-label="t('plugins.confirmSave')"
      :current-label="t('plugins.previewCurrent')"
      :current-text="previewCurrentText"
      :items="previewItems"
      :mode="previewMode"
      :next-label="t('plugins.previewNext')"
      :next-text="previewNextText"
      :restart-hint="t('plugins.settingsRestartHint')"
      :saving="previewSaving"
      :title="previewTitle"
      @cancel="previewDialogVisible = false"
      @confirm="confirmPreviewSave"
    />
  </div>
</template>

<script setup lang="ts">
  import type { RawSettingsResponse } from '@/api/settings'
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import { getErrorMessage } from '@/api/client'
  import {
    type DriverConfigItem,
    getCoreSettings,
    getCoreSettingsRaw,
    getDriverConfig,
    updateCoreSettings,
    updateCoreSettingsRaw,
    validateCoreSettingsRaw,
  } from '@/api/core'
  import { useRawTomlValidation } from '@/composables/useRawTomlValidation'
  import { useNoticeStore } from '@/stores/notice'
  import { useRestartStore } from '@/stores/restart'
  import AdapterManagementPanel from '@/views/core/AdapterManagementPanel.vue'
  import { useCoreRouteState } from '@/views/core/routeState'
  import RawSettingsEditor from '@/views/plugins/RawSettingsEditor.vue'
  import {
    buildRevertValues,
    buildSettingsPreviewItems,
    displayChoiceTitle,
    displayFieldValue,
    type PluginSettingField,
  } from '@/views/plugins/settingsEditor'
  import SettingsFieldEditor from '@/views/plugins/SettingsFieldEditor.vue'
  import SettingsModeBar from '@/views/plugins/SettingsModeBar.vue'
  import SettingsPreviewDialog from '@/views/plugins/SettingsPreviewDialog.vue'
  import { useSettingsEditor } from '@/views/plugins/useSettingsEditor'

  const loading = ref(false)
  const errorMessage = ref('')
  const adapterManagementPanel = ref<{ reload: () => Promise<void> } | null>(null)
  const driverBuiltin = ref<DriverConfigItem[]>([])
  const coreEditorMode = ref<'basic' | 'advanced'>('basic')
  const coreRawText = ref('')
  const coreRawInitialText = ref('')
  const coreRawLoading = ref(false)
  const coreRawSaving = ref(false)
  const coreRawErrorMessage = ref('')
  const previewDialogVisible = ref(false)
  const previewMode = ref<'basic' | 'raw'>('basic')
  const previewAction = ref<'core-basic' | 'core-raw'>('core-basic')
  const noticeStore = useNoticeStore()
  const restartStore = useRestartStore()
  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const { sectionTab } = useCoreRouteState(route, router)

  const coreEditor = useSettingsEditor({
    load: getCoreSettings,
    save: payload => updateCoreSettings(payload),
    messages: {
      invalidJson: t('plugins.settingsInvalidJson'),
      loadFailed: t('plugins.settingsLoadFailed'),
      saveFailed: t('plugins.settingsSaveFailed'),
      saveSuccess: t('plugins.settingsSaved'),
    },
    afterSave: ({ previousState, values, clear }) => {
      restartStore.markPending({
        id: 'core:settings',
        scope: 'core',
        summary: t('restart.pendingCoreSettings'),
        undo: {
          kind: 'core-settings',
          values: buildRevertValues(previousState.fields, values, clear),
        },
      })
    },
  })

  const coreLoading = coreEditor.loading
  const coreSaving = coreEditor.saving
  const coreErrorMessage = coreEditor.errorMessage
  const coreSettings = coreEditor.state
  const coreFields = coreEditor.fields
  const coreForm = coreEditor.form
  const hasPendingCoreChanges = coreEditor.hasPendingChanges
  const hasPendingCoreRawChanges = computed(() => coreRawText.value !== coreRawInitialText.value)
  const previewSaving = computed(() => coreSaving.value || coreRawSaving.value)
  const previewTitle = computed(() =>
    previewMode.value === 'basic' ? t('plugins.previewChangesTitle') : t('plugins.previewRawTitle'),
  )
  const previewCurrentText = computed(() => coreRawInitialText.value)
  const previewNextText = computed(() => coreRawText.value)
  const previewItems = computed(() =>
    buildSettingsPreviewItems(
      coreFields.value,
      coreForm.value,
      coreEditor.draftOverrides.value,
      coreEditor.draftClears.value,
      t('plugins.settingsInvalidJson'),
    ),
  )
  const {
    validateNow: validateCoreRawNow,
    validationColumn: coreRawValidationColumn,
    validationLine: coreRawValidationLine,
    validationMessage: coreRawValidationMessage,
    validationPending: coreRawValidationPending,
  } = useRawTomlValidation({
    text: coreRawText,
    initialText: coreRawInitialText,
    fallbackMessage: t('plugins.settingsRawValidateFailed'),
    validate: async text => (await validateCoreSettingsRaw({ text })).data,
  })

  function settingsValueSourceLabel (source: string) {
    const map: Record<string, string> = {
      default: t('plugins.settingsValueSourceDefault'),
      plugin_section: t('plugins.settingsValueSourcePlugin'),
      legacy_global: t('plugins.settingsValueSourceLegacy'),
      env: t('plugins.settingsValueSourceEnv'),
    }
    return map[source] || source
  }

  function formatFieldChoices (choices: Array<{ title: string, value: unknown }>) {
    const normalized = choices
      .map(choice => displayChoiceTitle(choice))
      .filter(Boolean)

    if (normalized.length <= 4) {
      return normalized.join(' / ')
    }

    return `${normalized.slice(0, 4).join(' / ')} +${normalized.length - 4}`
  }

  function applyCoreRawState (nextState: RawSettingsResponse) {
    coreRawText.value = nextState.text
    coreRawInitialText.value = nextState.text
  }

  async function loadCoreRawSettings () {
    coreRawLoading.value = true
    coreRawErrorMessage.value = ''
    try {
      const response = await getCoreSettingsRaw()
      applyCoreRawState(response.data)
    } catch (error) {
      coreRawErrorMessage.value = getErrorMessage(error, t('plugins.settingsRawLoadFailed'))
    } finally {
      coreRawLoading.value = false
    }
  }

  async function loadDriverManagement () {
    errorMessage.value = ''
    try {
      const driverConfigResponse = await getDriverConfig()
      driverBuiltin.value = driverConfigResponse.data.builtin
    } catch (error) {
      errorMessage.value = getErrorMessage(error, t('core.loadFailed'))
    }
  }

  async function loadCoreManagement () {
    coreLoading.value = true
    coreRawLoading.value = true
    coreErrorMessage.value = ''
    coreRawErrorMessage.value = ''
    try {
      const coreResponse = await getCoreSettings()
      coreEditor.applyState(coreResponse.data)
      coreErrorMessage.value = ''
    } catch (error) {
      coreErrorMessage.value = getErrorMessage(error, t('plugins.settingsLoadFailed'))
    } finally {
      coreLoading.value = false
    }

    await loadCoreRawSettings()
  }

  function driverChipColor (item: DriverConfigItem) {
    return item.is_active ? 'success' : 'warning'
  }

  function driverStatusText (item: DriverConfigItem) {
    return item.is_active ? t('plugins.driverActive') : t('plugins.driverRegisteredOnly')
  }

  async function clearCoreField (field: PluginSettingField) {
    coreEditor.clearField(field)
  }

  async function saveCoreSettings () {
    if (!coreSettings.value) return
    await coreEditor.submit()
  }

  function openCoreSettingsPreview () {
    if (!coreSettings.value) return
    const items = previewItems.value
    if (items.length === 0) return
    previewMode.value = 'basic'
    previewAction.value = 'core-basic'
    previewDialogVisible.value = true
  }

  async function saveCoreRawSettings () {
    if (!hasPendingCoreRawChanges.value) return
    coreRawSaving.value = true
    coreRawErrorMessage.value = ''
    const previousText = coreRawInitialText.value
    try {
      const rawResponse = await updateCoreSettingsRaw({ text: coreRawText.value })
      const settingsResponse = await getCoreSettings()
      applyCoreRawState(rawResponse.data)
      coreEditor.applyState(settingsResponse.data)
      restartStore.markPending({
        id: 'core:raw',
        scope: 'core',
        summary: t('restart.pendingCoreRaw'),
        undo: {
          kind: 'core-raw',
          text: previousText,
        },
      })
      noticeStore.show(t('plugins.settingsRawSaved'), 'success')
    } catch (error) {
      const message = getErrorMessage(error, t('plugins.settingsRawSaveFailed'))
      coreRawErrorMessage.value = message
      noticeStore.show(message, 'error')
    } finally {
      coreRawSaving.value = false
    }
  }

  async function openCoreRawPreview () {
    if (!hasPendingCoreRawChanges.value) return
    if (!await validateCoreRawNow()) return
    previewMode.value = 'raw'
    previewAction.value = 'core-raw'
    previewDialogVisible.value = true
  }

  async function confirmPreviewSave () {
    await (previewAction.value === 'core-basic' ? saveCoreSettings() : saveCoreRawSettings())

    if (!coreErrorMessage.value && !coreRawErrorMessage.value) {
      previewDialogVisible.value = false
    }
  }

  async function handleRefresh () {
    loading.value = true
    try {
      await Promise.all([
        loadDriverManagement(),
        loadCoreManagement(),
        adapterManagementPanel.value?.reload() || Promise.resolve(),
      ])
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    loading.value = true
    void Promise.all([
      loadDriverManagement(),
      loadCoreManagement(),
    ]).finally(() => {
      loading.value = false
    })
  })
</script>

<style scoped>
.settings-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-shell__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.settings-shell__headline {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.settings-list-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: var(--shape-medium);
}

.settings-list-row {
  padding: 18px 20px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background:
    linear-gradient(180deg, rgba(var(--v-theme-surface), 0.98), rgba(var(--v-theme-surface), 0.98)),
    linear-gradient(135deg, rgba(var(--v-theme-primary), 0.02), rgba(var(--v-theme-secondary), 0.02));
}

.settings-list-row:last-child {
  border-bottom: 0;
}

.settings-list-row__main {
  display: grid;
  grid-template-columns: minmax(200px, 260px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.settings-list-row__info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.settings-list-row__label {
  line-height: 1.3;
  word-break: break-word;
}

.settings-list-row__description {
  line-height: 1.45;
}

.settings-list-row__status {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-height: 20px;
}

.settings-list-row__control {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  padding: 14px;
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-on-surface), 0.025);
  border: 1px solid rgba(var(--v-border-color), 0.65);
}

.settings-list-row__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex-wrap: wrap;
}

.settings-action {
  min-width: 68px;
}

.settings-action--primary {
  font-weight: 600;
}

.settings-list-row__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  line-height: 1.35;
  word-break: break-word;
}

.settings-list-row__control :deep(.settings-field-editor) {
  width: 100%;
}

.settings-list-row__control :deep(.v-field),
.settings-list-row__control :deep(.v-selection-control) {
  width: 100%;
}

.config-chip-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-height: 32px;
}

@media (max-width: 960px) {
  .settings-list-row__main {
    grid-template-columns: 1fr;
  }
}
</style>
