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
          v-if="authStore.isOwner"
          variant="tonal"
          @click="openPackageManager"
        >
          {{ t('core.adapterPackageManager') }}
        </v-btn>
        <v-btn variant="text" @click="addDraftRow">
          {{ t('core.addAdapterModule') }}
        </v-btn>
        <v-btn
          color="primary"
          :disabled="!hasPendingChanges"
          :loading="saving"
          @click="save"
        >
          {{ t('common.save') }}
        </v-btn>
      </div>
    </div>

    <v-alert v-if="errorMessage" density="comfortable" type="error" variant="tonal">
      {{ errorMessage }}
    </v-alert>

    <v-progress-linear v-if="loading" color="primary" indeterminate />

    <div v-else class="adapter-panel__rows">
      <section
        v-for="row in draftRows"
        :key="row.id"
        class="adapter-row"
      >
        <div class="adapter-row__field">
          <v-text-field
            v-model="row.value"
            density="comfortable"
            hide-details
            :label="t('core.adapterModuleLabel')"
            :placeholder="t('core.adapterModulePlaceholder')"
          />
          <div class="adapter-row__chips">
            <v-chip
              v-if="row.value.trim()"
              color="primary"
              size="x-small"
              variant="tonal"
            >
              {{ t('core.adapterConfigured') }}
            </v-chip>
            <v-chip
              v-if="rowState(row.value)"
              :color="rowState(row.value)?.is_importable ? 'success' : 'warning'"
              size="x-small"
              variant="tonal"
            >
              {{
                rowState(row.value)?.is_importable
                  ? t('core.adapterImportable')
                  : t('core.adapterUnavailable')
              }}
            </v-chip>
            <v-chip
              v-if="rowState(row.value)"
              :color="rowState(row.value)?.is_loaded ? 'success' : 'default'"
              size="x-small"
              variant="tonal"
            >
              {{
                rowState(row.value)?.is_loaded
                  ? t('core.adapterLoaded')
                  : t('core.adapterNotLoaded')
              }}
            </v-chip>
            <v-chip
              v-if="row.value.trim() && !rowState(row.value)"
              color="warning"
              size="x-small"
              variant="tonal"
            >
              {{ t('core.adapterUnsaved') }}
            </v-chip>
          </div>
          <div
            v-if="rowStatusSummary(row.value)"
            class="text-caption text-medium-emphasis"
          >
            {{ rowStatusSummary(row.value) }}
          </div>
        </div>

        <v-btn
          color="warning"
          icon="mdi-trash-can-outline"
          size="small"
          variant="text"
          @click="removeDraftRow(row.id)"
        />
      </section>

      <div v-if="draftRows.length === 0" class="adapter-panel__empty">
        {{ t('plugins.emptyAdapterModules') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { useAuthStore } from '@/stores/auth'
  import { useNoticeStore } from '@/stores/notice'
  import { useRestartStore } from '@/stores/restart'
  import { useAdapterManagement } from '@/views/core/useAdapterManagement'

  const { t } = useI18n()
  const router = useRouter()
  const authStore = useAuthStore()
  const noticeStore = useNoticeStore()
  const restartStore = useRestartStore()
  const {
    adapterCount,
    addDraftRow,
    draftRows,
    errorMessage,
    hasPendingChanges,
    loading,
    reload,
    removeDraftRow,
    rowState,
    rowStatusSummary,
    save,
    saving,
  } = useAdapterManagement({
    noticeStore,
    restartStore,
    t,
  })

  function openPackageManager () {
    void router.push({ name: 'adapters-store' })
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
}

.adapter-panel__rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.adapter-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 14px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-on-surface), 0.02);
}

.adapter-row__field {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.adapter-row__chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.adapter-panel__empty {
  padding: 20px;
  border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: var(--shape-medium);
  color: rgba(var(--v-theme-on-surface), 0.65);
  text-align: center;
}

@media (max-width: 760px) {
  .adapter-row {
    grid-template-columns: 1fr;
  }
}
</style>
