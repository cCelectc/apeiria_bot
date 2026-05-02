<template>
  <div class="adapter-panel">
    <div class="adapter-panel__header">
      <div class="adapter-panel__headline">
        <div class="text-subtitle-1 font-weight-medium">{{ t('core.adaptersTab') }}</div>
        <div class="text-body-2 text-medium-emphasis">
          {{ t('core.adapterConfigDescription') }}
        </div>
      </div>

      <div class="adapter-panel__actions">
        <v-sheet class="summary-card">
          <div class="summary-card__label">{{ t('plugins.adapterCount') }}</div>
          <div class="summary-card__value">{{ adapterCount }}</div>
        </v-sheet>
        <v-btn
          prepend-icon="mdi-tune-variant"
          variant="tonal"
          @click="adapterConfigDialogVisible = true"
        >
          {{ t('core.adapterOverviewAdvancedAction') }}
        </v-btn>
        <v-btn
          v-if="authStore.isOwner"
          prepend-icon="mdi-package-variant-closed"
          variant="tonal"
          @click="openPackageManager"
        >
          {{ t('core.adapterPackageManager') }}
        </v-btn>
      </div>
    </div>

    <v-alert v-if="errorMessage" density="comfortable" type="error" variant="tonal">
      {{ errorMessage }}
    </v-alert>

    <v-progress-linear v-if="loading" color="primary" indeterminate />

    <div v-else>
      <div v-if="configuredModules.length > 0" class="adapter-overview">
        <div class="adapter-overview-strip">
          <div class="adapter-overview-strip__item">
            <v-icon icon="mdi-power-plug-outline" size="20" />
            <div>
              <div class="adapter-overview-strip__title">{{ t('core.adapterOverviewRuntimeTitle') }}</div>
              <div class="adapter-overview-strip__value">
                {{ t('core.adapterOverviewRuntimeValue', { loaded: loadedAdapterCount, total: adapterCount }) }}
              </div>
              <div class="adapter-overview-strip__text">{{ t('core.adapterOverviewRuntimeText') }}</div>
            </div>
          </div>

          <div class="adapter-overview-strip__item">
            <v-icon icon="mdi-file-tree-outline" size="20" />
            <div>
              <div class="adapter-overview-strip__title">{{ t('core.adapterOverviewConfigTitle') }}</div>
              <div class="adapter-overview-strip__value">
                {{ t('core.adapterOverviewConfigValue', { total: adapterCount }) }}
              </div>
              <div class="adapter-overview-strip__text">{{ t('core.adapterOverviewConfigText') }}</div>
            </div>
          </div>

          <div
            class="adapter-overview-strip__item"
            :class="{ 'adapter-overview-strip__item--warning': unavailableAdapterCount > 0 }"
          >
            <v-icon :icon="unavailableAdapterCount > 0 ? 'mdi-alert-outline' : 'mdi-restart'" size="20" />
            <div>
              <div class="adapter-overview-strip__title">{{ t('core.adapterOverviewRestartTitle') }}</div>
              <div class="adapter-overview-strip__value">
                {{
                  unavailableAdapterCount > 0
                    ? t('core.adapterOverviewUnavailableValue', { total: unavailableAdapterCount })
                    : t('core.adapterOverviewRestartValue')
                }}
              </div>
              <div class="adapter-overview-strip__text">{{ t('core.adapterOverviewRestartText') }}</div>
            </div>
          </div>
        </div>

        <section :aria-label="t('core.adapterOverviewListTitle')" class="adapter-status-list">
          <div class="adapter-status-list__header">
            <div>
              <div class="adapter-status-list__title">{{ t('core.adapterOverviewListTitle') }}</div>
              <div class="adapter-status-list__description">
                {{ t('core.adapterOverviewListDescription') }}
              </div>
            </div>
          </div>

          <article
            v-for="item in configuredModules"
            :key="item.name"
            class="adapter-status-row"
          >
            <div class="adapter-status-row__signal" :class="adapterStatusSignalClass(item)">
              <v-icon :icon="adapterStatusIcon(item)" size="18" />
            </div>

            <div class="adapter-status-row__main">
              <div class="adapter-status-row__title-line">
                <h2 class="adapter-status-row__title">{{ adapterDisplayName(item.name) }}</h2>
                <div class="adapter-status-row__chips">
                  <v-chip
                    :color="item.is_loaded ? 'success' : 'default'"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ item.is_loaded ? t('core.adapterLoaded') : t('core.adapterNotLoaded') }}
                  </v-chip>
                  <v-chip
                    :color="item.is_importable ? 'success' : 'warning'"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ item.is_importable ? t('core.adapterImportable') : t('core.adapterUnavailable') }}
                  </v-chip>
                  <v-chip color="primary" size="x-small" variant="tonal">
                    {{ t('core.adapterConfigured') }}
                  </v-chip>
                </div>
              </div>

              <div class="adapter-status-row__module">{{ item.name }}</div>
              <div class="adapter-status-row__summary">{{ adapterStatusSummaryForItem(item) }}</div>
            </div>

            <v-tooltip location="top">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  :aria-label="t('core.adapterOverviewAdvancedAction')"
                  class="adapter-status-row__action"
                  color="primary"
                  icon="mdi-tune-variant"
                  size="small"
                  variant="text"
                  @click="adapterConfigDialogVisible = true"
                />
              </template>
              {{ t('core.adapterOverviewAdvancedAction') }}
            </v-tooltip>
          </article>
        </section>
      </div>
      <EmptyState
        v-else
        icon="mdi-connection"
        :text="t('core.adapterEmptyText')"
        :title="t('plugins.emptyAdapterModules')"
      >
        <template #actions>
          <v-btn prepend-icon="mdi-tune-variant" variant="tonal" @click="openAdapterConfigWithNewRow">
            {{ t('core.adapterOverviewEmptyAction') }}
          </v-btn>
          <v-btn
            v-if="authStore.isOwner"
            prepend-icon="mdi-package-variant-closed"
            variant="text"
            @click="openPackageManager"
          >
            {{ t('core.adapterPackageManager') }}
          </v-btn>
        </template>
      </EmptyState>
    </div>

    <v-dialog v-model="adapterConfigDialogVisible" max-width="860">
      <v-card>
        <v-card-title class="adapter-config-dialog__header">
          <div>
            <div>{{ t('core.adapterOverviewAdvancedAction') }}</div>
            <div class="text-caption text-medium-emphasis">
              {{ t('core.adapterModuleHelper') }}
            </div>
          </div>
        </v-card-title>
        <v-card-text class="d-flex flex-column ga-4">
          <v-alert
            v-if="hasPendingChanges || normalizationNotes.length > 0"
            density="comfortable"
            type="warning"
            variant="tonal"
          >
            <div class="adapter-panel__diagnostic-summary">
              <span>{{ adapterDiagnosticsSummary }}</span>
              <span v-if="normalizationNotes.length > 0">{{ normalizationNotes.join(' ') }}</span>
            </div>
          </v-alert>

          <div class="adapter-panel__rows">
            <section
              v-for="row in draftRows"
              :key="row.id"
              class="adapter-row"
            >
              <label class="adapter-row__field workbench-field">
                <span class="workbench-field__title">{{ t('core.adapterModuleLabel') }}</span>
                <span class="workbench-field__helper">{{ t('core.adapterModuleHelper') }}</span>
                <v-text-field
                  v-model="row.value"
                  :aria-label="t('core.adapterModuleLabel')"
                  class="workbench-field__control"
                  density="compact"
                  hide-details
                  :placeholder="t('core.adapterModulePlaceholder')"
                  variant="outlined"
                />
                <div
                  v-if="rowStatusSummary(row.value)"
                  class="text-caption text-medium-emphasis"
                >
                  {{ rowStatusSummary(row.value) }}
                </div>
              </label>

              <v-btn
                color="warning"
                icon="mdi-trash-can-outline"
                size="small"
                variant="text"
                @click="removeDraftRow(row.id)"
              />
            </section>
          </div>

          <v-btn
            class="align-self-start"
            prepend-icon="mdi-plus"
            variant="text"
            @click="addDraftRow"
          >
            {{ t('core.addAdapterModule') }}
          </v-btn>

          <v-expansion-panels
            v-if="hasAdapterDiagnostics"
            class="adapter-panel__advanced"
            variant="accordion"
          >
            <v-expansion-panel>
              <v-expansion-panel-title>{{ t('core.adapterDiagnosticsAdvanced') }}</v-expansion-panel-title>
              <v-expansion-panel-text>
                <div class="adapter-diagnostics">
                  <div class="adapter-diagnostics__group">
                    <div class="adapter-diagnostics__label">{{ t('core.adapterPreviewNext') }}</div>
                    <div class="adapter-diagnostics__value">{{ formatModuleList(previewNextModules) }}</div>
                  </div>
                  <div v-if="addedModules.length > 0" class="adapter-diagnostics__group">
                    <div class="adapter-diagnostics__label">{{ t('core.adapterPreviewAdded') }}</div>
                    <div class="adapter-diagnostics__value">{{ formatModuleList(addedModules) }}</div>
                  </div>
                  <div v-if="removedModules.length > 0" class="adapter-diagnostics__group">
                    <div class="adapter-diagnostics__label">{{ t('core.adapterPreviewRemoved') }}</div>
                    <div class="adapter-diagnostics__value">{{ formatModuleList(removedModules) }}</div>
                  </div>
                  <div v-if="duplicateModules.length > 0" class="adapter-diagnostics__group">
                    <div class="adapter-diagnostics__label">{{ t('core.adapterDuplicateModules') }}</div>
                    <div class="adapter-diagnostics__value">{{ formatModuleList(duplicateModules) }}</div>
                  </div>
                  <div v-if="blankRowCount > 0" class="adapter-diagnostics__group">
                    <div class="adapter-diagnostics__label">{{ t('core.adapterBlankRows') }}</div>
                    <div class="adapter-diagnostics__value">{{ blankRowCount }}</div>
                  </div>
                  <div v-if="unchangedModules.length > 0" class="adapter-diagnostics__group">
                    <div class="adapter-diagnostics__label">{{ t('core.adapterUnchangedModules') }}</div>
                    <div class="adapter-diagnostics__value">{{ formatModuleList(unchangedModules) }}</div>
                  </div>
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="adapterConfigDialogVisible = false">{{ t('common.close') }}</v-btn>
          <v-spacer />
          <v-btn
            color="primary"
            :disabled="!hasPendingChanges"
            :loading="saving"
            @click="openAdapterPreview"
          >
            {{ t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="adapterPreviewVisible" max-width="720">
      <v-card>
        <v-card-title>{{ t('core.adapterPreviewTitle') }}</v-card-title>
        <v-card-text class="d-flex flex-column ga-4">
          <v-alert density="comfortable" type="warning" variant="tonal">
            {{ t('core.adapterRestartRequired') }}
          </v-alert>

          <div class="adapter-preview-grid">
            <div
              v-for="item in previewItems"
              :key="item.key"
              class="adapter-preview-block"
            >
              <div class="adapter-preview-block__label">{{ item.key }}</div>
              <pre class="adapter-preview-block__code">{{ formatModuleList(item.value) }}</pre>
            </div>
          </div>

          <div v-if="normalizationNotes.length > 0" class="adapter-preview-notes">
            <div class="adapter-preview-block__label">{{ t('core.adapterNormalizationNotes') }}</div>
            <ul>
              <li v-for="note in normalizationNotes" :key="note">{{ note }}</li>
            </ul>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="adapterPreviewVisible = false">{{ t('common.cancel') }}</v-btn>
          <v-spacer />
          <v-btn color="primary" :loading="saving" @click="confirmAdapterPreviewSave">
            {{ t('plugins.confirmSave') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
  import type { AdapterConfigItem } from '@/api/adapters'
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { EmptyState } from '@/components/workbench'
  import { useAuthStore } from '@/stores/auth'
  import { useNoticeStore } from '@/stores/notice'
  import { useRestartStore } from '@/stores/restart'
  import { useAdapterManagement } from '@/views/core/useAdapterManagement'

  const { t } = useI18n()
  const router = useRouter()
  const authStore = useAuthStore()
  const noticeStore = useNoticeStore()
  const restartStore = useRestartStore()
  const adapterConfigDialogVisible = ref(false)
  const adapterPreviewVisible = ref(false)
  const {
    addedModules,
    adapterCount,
    addDraftRow,
    blankRowCount,
    configuredModules,
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
    rowStatusSummary,
    save,
    saving,
    unchangedModules,
  } = useAdapterManagement({
    noticeStore,
    restartStore,
    t,
  })
  const previewNextModules = computed(() => previewItems.value[1]?.value ?? [])
  const hasAdapterDiagnostics = computed(() =>
    hasPendingChanges.value
    || blankRowCount.value > 0
    || duplicateModules.value.length > 0
    || unchangedModules.value.length > 0,
  )
  const adapterDiagnosticsSummary = computed(() => {
    if (!hasPendingChanges.value && normalizationNotes.value.length === 0) {
      return t('core.adapterDiagnosticsClean')
    }
    return t('core.adapterDiagnosticsSummary', {
      added: addedModules.value.length,
      removed: removedModules.value.length,
      total: previewNextModules.value.length,
    })
  })
  const loadedAdapterCount = computed(() =>
    configuredModules.value.filter(item => item.is_loaded).length,
  )
  const unavailableAdapterCount = computed(() =>
    configuredModules.value.filter(item => !item.is_importable).length,
  )

  function openPackageManager () {
    void router.push({ name: 'adapters-store' })
  }

  function formatModuleList (modules: string[]) {
    return modules.length > 0 ? modules.join('\n') : t('common.none')
  }

  function adapterDisplayName (moduleName: string) {
    return moduleName.split('.').at(-1) || moduleName
  }

  function adapterStatusSummaryForItem (item: AdapterConfigItem) {
    return rowStatusSummary(item.name)
  }

  function adapterStatusIcon (item: AdapterConfigItem) {
    if (!item.is_importable) return 'mdi-alert-outline'
    return item.is_loaded ? 'mdi-check-circle-outline' : 'mdi-clock-outline'
  }

  function adapterStatusSignalClass (item: AdapterConfigItem) {
    if (!item.is_importable) return 'adapter-status-row__signal--warning'
    return item.is_loaded
      ? 'adapter-status-row__signal--success'
      : 'adapter-status-row__signal--idle'
  }

  function openAdapterConfigWithNewRow () {
    if (draftRows.value.length === 0) {
      addDraftRow()
    }
    adapterConfigDialogVisible.value = true
  }

  function openAdapterPreview () {
    if (!hasPendingChanges.value) return
    adapterPreviewVisible.value = true
  }

  async function confirmAdapterPreviewSave () {
    const saved = await save()
    if (saved) {
      adapterPreviewVisible.value = false
      adapterConfigDialogVisible.value = false
    }
  }

  defineExpose({
    reload,
  })

  onMounted(() => {
    void reload()
  })
</script>

<style scoped>
.adapter-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.adapter-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.adapter-panel__headline {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.adapter-panel__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.adapter-overview {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.adapter-overview-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-outline), 0.14);
  border-radius: var(--shape-medium);
  background: rgb(var(--v-theme-surface-container-low));
}

.adapter-overview-strip__item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
  padding: 14px 16px;
  border-inline-end: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.adapter-overview-strip__item:last-child {
  border-inline-end: 0;
}

.adapter-overview-strip__item .v-icon {
  margin-top: 1px;
  color: rgb(var(--v-theme-primary));
}

.adapter-overview-strip__item--warning .v-icon {
  color: rgb(var(--v-theme-warning));
}

.adapter-overview-strip__title {
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 0.78rem;
  font-weight: 700;
  line-height: 1.25;
}

.adapter-overview-strip__value {
  margin-top: 4px;
  color: rgb(var(--v-theme-on-surface));
  font-size: 1.05rem;
  font-weight: 750;
  line-height: 1.2;
}

.adapter-overview-strip__text {
  margin-top: 3px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.8rem;
  line-height: 1.35;
}

.adapter-status-list {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-outline), 0.14);
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-surface), 0.9);
}

.adapter-status-list__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
  background: rgba(var(--v-theme-surface-container-low), 0.72);
}

.adapter-status-list__title {
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.92rem;
  font-weight: 700;
  line-height: 1.3;
}

.adapter-status-list__description {
  margin-top: 3px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.82rem;
  line-height: 1.4;
}

.adapter-status-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.1);
  transition:
    background-color var(--motion-fast) var(--motion-ease),
    box-shadow var(--motion-fast) var(--motion-ease);
}

.adapter-status-row:last-child {
  border-bottom: 0;
}

.adapter-status-row:hover {
  background: rgba(var(--v-theme-surface-container-low), 0.54);
}

.adapter-status-row__signal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--shape-compact);
  background: rgba(var(--v-theme-on-surface), 0.05);
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.adapter-status-row__signal--success {
  background: rgba(var(--v-theme-success), 0.12);
  color: rgb(var(--v-theme-success));
}

.adapter-status-row__signal--warning {
  background: rgba(var(--v-theme-warning), 0.14);
  color: rgb(var(--v-theme-warning));
}

.adapter-status-row__signal--idle {
  background: rgba(var(--v-theme-outline), 0.1);
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.adapter-status-row__main {
  min-width: 0;
}

.adapter-status-row__title-line,
.adapter-status-row__chips {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.adapter-status-row__title {
  margin: 0;
  color: rgb(var(--v-theme-on-surface));
  font-size: 1rem;
  font-weight: 750;
  line-height: 1.25;
}

.adapter-status-row__module {
  margin-top: 3px;
  color: rgba(var(--v-theme-on-surface), 0.7);
  font-family: var(--font-family-mono);
  font-size: 0.82rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.adapter-status-row__summary {
  margin-top: 2px;
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 0.8rem;
  line-height: 1.35;
}

.adapter-status-row__action {
  align-self: center;
}

.adapter-panel__rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.adapter-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: start;
  padding: 16px;
  border: 1px solid rgba(var(--v-theme-outline), 0.16);
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-surface), 0.78);
}

.adapter-row__field {
  min-width: 0;
}

.adapter-panel__diagnostic-summary {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.adapter-panel__advanced {
  margin-top: 2px;
}

.adapter-diagnostics {
  display: grid;
  gap: 12px;
}

.adapter-diagnostics__group {
  display: grid;
  gap: 4px;
}

.adapter-diagnostics__label,
.adapter-preview-block__label {
  color: rgba(var(--v-theme-on-surface), 0.66);
  font-size: 0.78rem;
  font-weight: 700;
  line-height: 1.35;
}

.adapter-diagnostics__value {
  color: rgb(var(--v-theme-on-surface));
  font-family: var(--font-family-mono);
  font-size: 0.84rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.adapter-preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.adapter-preview-block {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 8px;
}

.adapter-preview-block__code {
  min-height: 80px;
  margin: 0;
  padding: 12px;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: var(--shape-compact);
  background: rgba(var(--v-theme-surface), 0.88);
  font-family: var(--font-family-mono);
  font-size: 0.84rem;
  white-space: pre-wrap;
  word-break: break-word;
}

.adapter-preview-notes ul {
  margin: 8px 0 0;
  padding-inline-start: 20px;
}

@media (max-width: 760px) {
  .adapter-overview-strip {
    grid-template-columns: 1fr;
  }

  .adapter-overview-strip__item {
    border-inline-end: 0;
    border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
  }

  .adapter-overview-strip__item:last-child {
    border-bottom: 0;
  }

  .adapter-status-row {
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: start;
  }

  .adapter-status-row__action {
    justify-self: end;
  }

  .adapter-row,
  .adapter-preview-grid {
    grid-template-columns: 1fr;
  }

  .adapter-panel__actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
