<template>
  <div>
    <div class="d-flex justify-space-between align-center mb-3">
      <div class="text-subtitle-1 font-weight-medium">
        {{ t('ai.sourcesTitle') }}
      </div>
      <v-btn color="primary" variant="tonal" @click="startCreateSource">
        {{ t('ai.createSource') }}
      </v-btn>
    </div>
    <v-sheet class="surface-gradient-card pa-2 source-list-panel" rounded="lg">
      <template v-if="sources.length > 0">
        <v-list class="bg-transparent" density="comfortable" lines="two">
          <v-list-item
            v-for="item in sources"
            :key="item.source_id"
            :active="item.source_id === activeSourceId"
            class="source-list-item"
            rounded="lg"
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
      </div>
    </v-sheet>
  </div>
</template>

<script setup lang="ts">
  import type { AISourceItem } from '@/api/ai/types'
  import { useI18n } from 'vue-i18n'

  defineProps<{
    activeSourceId: string
    removeSourceItem: (item: AISourceItem) => void | Promise<void>
    selectSource: (item: AISourceItem) => void | Promise<void>
    sourcePresetInitial: (value: string) => string
    sourcePresetLabel: (value: string) => string
    sources: AISourceItem[]
    startCreateSource: () => void
  }>()

  const { t } = useI18n()
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
</style>
