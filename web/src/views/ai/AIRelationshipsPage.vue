<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.relationships')"
    :title="t('ai.relationshipTab')"
  >
    <template #actions>
      <v-btn :loading="loading" variant="tonal" @click="loadData">
        {{ t('common.refresh') }}
      </v-btn>
    </template>

    <v-card class="page-panel">
      <v-card-text>
        <AIRelationshipsPanel
          v-model:relationship-form="relationshipForm"
          :load-recent-targets="loadRecentTargets"
          :load-relationship-for-target="loadRelationshipForTarget"
          :loading-recent-targets="loadingRecentTargets"
          :loading-relationship-events="loadingRelationshipEvents"
          :loading-selected-relationship="loadingSelectedRelationship"
          :open-chat-view="openChatView"
          :open-debug-conversations="openDebugConversations"
          :recent-targets="recentTargets"
          :relationship="relationship"
          :relationship-events="relationshipEvents"
          :save-relationship="saveRelationship"
          :saving-relationship="savingRelationship"
          :select-relationship="selectRelationship"
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
  import { useAIRelationshipTab } from '@/composables/useAIRelationshipTab'
  import AIRelationshipsPanel from '@/views/ai/AIRelationshipsPanel.vue'
  import { useAIPageLoader } from '@/views/ai/pageHelpers'

  const { t } = useI18n()
  const router = useRouter()
  const { errorMessage, loading, runPageLoad } = useAIPageLoader(() => t('ai.loadFailed'))

  const {
    loadRecentTargets,
    loadingRecentTargets,
    recentTargets,
  } = useAIMemoryTab(t)

  const {
    loadRelationshipForTarget,
    loadingRelationshipEvents,
    loadRelationships,
    loadingSelectedRelationship,
    relationship,
    relationshipEvents,
    relationshipForm,
    saveRelationship,
    savingRelationship,
    selectRelationship,
  } = useAIRelationshipTab(t)

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
      await Promise.all([
        loadRecentTargets(),
        loadRelationships(),
      ])
    })
  }

  onMounted(() => {
    void loadData()
  })
</script>
