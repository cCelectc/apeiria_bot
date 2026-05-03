<template>
  <div class="source-list-panel">
    <SelectableList
      :subtitle="t('ai.sourceListHint')"
      :title="t('ai.sourcesTitle')"
    >
      <template #actions>
        <v-btn color="primary" prepend-icon="mdi-server-plus" variant="tonal" @click="openSourcePresetDialog">
          {{ t('ai.createSource') }}
        </v-btn>
      </template>

      <template v-if="sources.length > 0">
        <SelectableListItem
          v-for="item in sources"
          :key="item.source_id"
          :active="item.source_id === activeSourceId"
          :subtitle="item.api_base || t('common.none')"
          :title="item.name"
          :warning="!item.enabled"
          @click="selectSource(item)"
        >
          <template #meta>
            <v-chip
              :color="item.enabled ? 'success' : 'default'"
              size="x-small"
              variant="tonal"
            >
              {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
            </v-chip>
            <v-chip color="primary" size="x-small" variant="tonal">
              {{ sourcePresetLabel(item.preset_type) }}
            </v-chip>
            <v-menu location="bottom end" offset="8">
              <template #activator="{ props: menuProps }">
                <v-btn
                  v-bind="menuProps"
                  :aria-label="t('common.moreActions')"
                  density="comfortable"
                  icon="mdi-dots-horizontal"
                  size="small"
                  variant="text"
                  @click.stop
                />
              </template>
              <v-list density="compact">
                <v-list-item
                  base-color="error"
                  prepend-icon="mdi-delete-outline"
                  :title="t('common.delete')"
                  @click="removeSourceItem(item)"
                />
              </v-list>
            </v-menu>
          </template>
        </SelectableListItem>
      </template>

      <EmptyState
        v-else
        action-icon="mdi-server-plus"
        :action-label="emptyActionLabel"
        icon="mdi-server-network-off"
        :text="t('ai.noSourcesHint')"
        :title="t('ai.noSources')"
        @action="openSourcePresetDialog"
      />
    </SelectableList>

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
  import {
    EmptyState,
    SelectableList,
    SelectableListItem,
  } from '@/components/workbench'

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
  min-width: 0;
  min-height: 100%;
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
