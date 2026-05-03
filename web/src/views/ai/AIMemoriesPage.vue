<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.memories')"
    :title="t('ai.memoryTab')"
  >
    <template #actions>
      <v-btn :loading="loading" variant="tonal" @click="loadData">
        {{ t('common.refresh') }}
      </v-btn>
    </template>

    <v-card class="page-panel">
      <v-card-text>
        <AIMemoriesPanel
          v-model:memory-draft="memoryDraft"
          v-model:memory-edit-draft="memoryEditDraft"
          v-model:memory-form="memoryForm"
          :all-memories-selected="allMemoriesSelected"
          :bulk-action-loading="bulkActionLoading"
          :bulk-delete="bulkDeleteMemories"
          :bulk-set-ignored="bulkSetMemoriesIgnored"
          :can-load-memories="canLoadMemories"
          :can-save-edited-memory="canSaveEditedMemory"
          :can-save-memory="canSaveMemory"
          :cancel-edit-memory="cancelEditMemory"
          :clear-selection="clearMemorySelection"
          :deleting-memory-id="deletingMemoryId"
          :editing-memory-id="editingMemoryId"
          :load-memories="loadMemories"
          :load-recent-targets="loadRecentTargets"
          :loading-memories="loadingMemories"
          :loading-recent-targets="loadingRecentTargets"
          :memories="memories"
          :open-chat-view="openChatView"
          :open-debug-conversations="openDebugConversations"
          :recent-targets="recentTargets"
          :remove-memory="removeMemory"
          :save-edited-memory="saveEditedMemory"
          :save-memory="saveMemory"
          :saving-edited-memory-id="savingEditedMemoryId"
          :saving-memory="savingMemory"
          :select-recent-target="selectRecentTarget"
          :selected-memory-count="selectedMemoryCount"
          :selected-memory-ids="selectedMemoryIds"
          :selected-recent-target-id="selectedRecentTargetId"
          :start-edit-memory="startEditMemory"
          :toggle-ignored="toggleMemoryIgnored"
          :toggle-memory-selection="toggleMemorySelection"
          :toggle-select-all="toggleSelectAllMemories"
          :toggling-ignored-id="togglingIgnoredId"
        />
      </v-card-text>
    </v-card>
  </PageScaffold>
</template>

<script setup lang="ts">
  import { onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { PageScaffold } from '@/components/workbench'
  import { useAIMemoryTab } from '@/composables/useAIMemoryTab'
  import AIMemoriesPanel from '@/views/ai/AIMemoriesPanel.vue'
  import { useAIPageLoader } from '@/views/ai/pageHelpers'

  const { t } = useI18n()
  const router = useRouter()
  const { errorMessage, loading, runPageLoad } = useAIPageLoader(() => t('ai.loadFailed'))

  const {
    allMemoriesSelected,
    bulkActionLoading,
    bulkDelete: bulkDeleteMemories,
    bulkSetIgnored: bulkSetMemoriesIgnored,
    canLoadMemories,
    canSaveMemory,
    canSaveEditedMemory,
    cancelEditMemory,
    clearSelection: clearMemorySelection,
    deletingMemoryId,
    editingMemoryId,
    loadMemories,
    loadRecentTargets,
    loadingMemories,
    loadingRecentTargets,
    memoryEditDraft,
    memories,
    memoryDraft,
    memoryForm,
    recentTargets,
    removeMemory,
    saveMemory,
    saveEditedMemory,
    savingEditedMemoryId,
    savingMemory,
    selectedMemoryCount,
    selectedMemoryIds,
    selectRecentTarget,
    selectedRecentTargetId,
    startEditMemory,
    toggleIgnored: toggleMemoryIgnored,
    toggleMemorySelection,
    toggleSelectAll: toggleSelectAllMemories,
    togglingIgnoredId,
  } = useAIMemoryTab(t)

  function openDebugConversations () {
    void router.push({
      name: 'ai-debug',
      query: { debug: 'conversations' },
    })
  }

  async function openChatView () {
    await router.push({ name: 'chat' })
  }

  async function loadData () {
    await runPageLoad(async () => {
      await loadRecentTargets()
      await loadMemories()
    })
  }

  onMounted(() => {
    void loadData()
  })
</script>
