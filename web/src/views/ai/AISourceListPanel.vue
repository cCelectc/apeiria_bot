<template>
  <div>
    <div class="d-flex justify-space-between align-center mb-3">
      <div class="text-subtitle-1 font-weight-medium">
        {{ t('ai.sourcesTitle') }}
      </div>
      <v-btn color="primary" variant="tonal" @click="openSourcePresetDialog">
        {{ t('ai.createSource') }}
      </v-btn>
    </div>
    <v-sheet class="surface-gradient-card pa-2 source-list-panel">
      <template v-if="sources.length > 0">
        <v-list class="bg-transparent" density="comfortable" lines="two">
          <v-list-item
            v-for="item in sources"
            :key="item.source_id"
            :active="item.source_id === activeSourceId"
            class="source-list-item"
            @click="selectSource(item)"
          >
            <template #prepend>
              <v-avatar class="source-list-item__avatar" color="primary" size="36" variant="tonal">
                {{ sourcePresetInitial(item.preset_type) }}
              </v-avatar>
            </template>
            <div class="source-list-item__body">
              <div class="source-list-item__header">
                <v-list-item-title>{{ item.name }}</v-list-item-title>
                <v-chip
                  :color="item.enabled ? 'success' : 'default'"
                  size="x-small"
                  variant="tonal"
                >
                  {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
                </v-chip>
              </div>
              <v-list-item-subtitle class="source-list-item__subtitle">
                {{ item.api_base || t('common.none') }}
              </v-list-item-subtitle>
              <div class="source-list-item__meta">
                <v-chip color="primary" size="x-small" variant="tonal">
                  {{ sourcePresetLabel(item.preset_type) }}
                </v-chip>
              </div>
            </div>
            <template #append>
              <v-btn
                color="error"
                icon="mdi-delete-outline"
                size="small"
                variant="text"
                @click.stop="removeSourceItem(item)"
              />
            </template>
          </v-list-item>
        </v-list>
      </template>
      <div v-else class="pa-4">
        <div class="empty-state-text">{{ t('ai.noSources') }}</div>
        <div class="empty-state-hint mt-2">{{ t('ai.noSourcesHint') }}</div>
        <v-btn
          class="mt-4"
          color="primary"
          prepend-icon="mdi-server-plus"
          variant="tonal"
          @click="openSourcePresetDialog"
        >
          {{ emptyActionLabel }}
        </v-btn>
      </div>
    </v-sheet>

    <v-dialog v-model="sourcePresetDialog" max-width="840">
      <v-card class="source-preset-dialog">
        <v-card-title class="source-preset-dialog__header">
          <div>
            <div class="source-preset-dialog__title">
              {{ t('ai.sourcePresetDialogTitle') }}
            </div>
            <div class="source-preset-dialog__hint">
              {{ t('ai.sourcePresetDialogHint') }}
            </div>
          </div>
        </v-card-title>
        <v-card-text>
          <div v-if="sourcePresets.length > 0" class="source-preset-grid">
            <button
              v-for="preset in sourcePresets"
              :key="preset.preset_type"
              class="source-preset-card"
              type="button"
              @click="chooseSourcePreset(preset.preset_type)"
            >
              <v-avatar class="source-preset-card__avatar" color="primary" size="40" variant="tonal">
                {{ sourcePresetInitial(preset.preset_type) }}
              </v-avatar>
              <div class="source-preset-card__body">
                <div class="source-preset-card__title">
                  {{ preset.display_name }}
                </div>
                <div class="source-preset-card__text">
                  {{ preset.description || t('ai.sourcePresetDialogDefaultHint') }}
                </div>
                <div v-if="preset.default_api_base" class="source-preset-card__meta">
                  {{ preset.default_api_base }}
                </div>
              </div>
            </button>
          </div>
          <div v-else class="pa-4">
            <div class="empty-state-text">{{ t('ai.sourcePresetDialogEmpty') }}</div>
          </div>
        </v-card-text>
        <v-card-actions class="px-6 pb-6">
          <v-spacer />
          <v-btn variant="text" @click="sourcePresetDialog = false">
            {{ t('common.cancel') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
  import type { AISourceItem, AISourcePresetItem } from '@/api/ai/types'
  import { ref } from 'vue'
  import { useI18n } from 'vue-i18n'

  const props = defineProps<{
    activeSourceId: string
    emptyActionLabel: string
    removeSourceItem: (item: AISourceItem) => void | Promise<void>
    selectSource: (item: AISourceItem) => void | Promise<void>
    sourcePresetInitial: (value: string) => string
    sourcePresetLabel: (value: string) => string
    sourcePresets: AISourcePresetItem[]
    sources: AISourceItem[]
    startCreateSource: (presetType?: string) => void
  }>()

  const { t } = useI18n()
  const sourcePresetDialog = ref(false)

  function openSourcePresetDialog () {
    if (props.sourcePresets.length === 0) {
      props.startCreateSource()
      return
    }
    sourcePresetDialog.value = true
  }

  function chooseSourcePreset (presetType: string) {
    props.startCreateSource(presetType)
    sourcePresetDialog.value = false
  }
</script>

<style scoped>
.source-list-panel {
  min-height: 100%;
}

.source-list-item {
  margin-bottom: 6px;
}

.source-list-item__avatar {
  flex-shrink: 0;
}

.source-list-item__body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  width: 100%;
}

.source-list-item__header {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.source-list-item__subtitle {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-all;
}

.source-list-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-preset-dialog__header {
  padding: 24px 24px 6px;
}

.source-preset-dialog__title {
  color: rgb(var(--v-theme-on-surface));
  font-size: 1.15rem;
  font-weight: 720;
  line-height: 1.35;
}

.source-preset-dialog__hint {
  max-width: 68ch;
  margin-top: 6px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.88rem;
  line-height: 1.55;
}

.source-preset-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.source-preset-card {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(var(--v-theme-outline-variant), 0.28);
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-surface-container), 0.62);
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    transform 160ms ease;
}

.source-preset-card:hover {
  border-color: rgba(var(--v-theme-primary), 0.42);
  background: rgba(var(--v-theme-primary), 0.07);
  transform: translateY(-1px);
}

.source-preset-card:active {
  transform: translateY(0);
}

.source-preset-card__avatar {
  flex-shrink: 0;
}

.source-preset-card__body {
  min-width: 0;
}

.source-preset-card__title {
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.95rem;
  font-weight: 720;
  line-height: 1.35;
}

.source-preset-card__text {
  display: -webkit-box;
  margin-top: 4px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.82rem;
  line-height: 1.45;
  overflow: hidden;
}

.source-preset-card__meta {
  margin-top: 10px;
  color: rgba(var(--v-theme-on-surface), 0.48);
  font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.76rem;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
