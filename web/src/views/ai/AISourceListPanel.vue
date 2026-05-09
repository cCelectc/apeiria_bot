<template>
  <div class="source-list-panel">
    <SelectableList
      :subtitle="t('ai.sourceListHint')"
      :title="t('ai.sourcesTitle')"
    >
      <template #actions>
        <v-btn color="primary" prepend-icon="mdi-server-plus" variant="tonal" @click="startCreateSource()">
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
        @action="startCreateSource()"
      />
    </SelectableList>
  </div>
</template>

<script setup lang="ts">
  import type { AISourceItem } from '@/api/ai/types'
  import { useI18n } from 'vue-i18n'
  import {
    EmptyState,
    SelectableList,
    SelectableListItem,
  } from '@/components/workbench'

  defineProps<{
    activeSourceId: string
    emptyActionLabel: string
    removeSourceItem: (item: AISourceItem) => void | Promise<void>
    selectSource: (item: AISourceItem) => void | Promise<void>
    sourcePresetLabel: (value: string) => string
    sources: AISourceItem[]
    startCreateSource: (presetType?: string) => void
  }>()

  const { t } = useI18n()
</script>

<style scoped>
.source-list-panel {
  min-width: 0;
  min-height: 100%;
}
</style>
