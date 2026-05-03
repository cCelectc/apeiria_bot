<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.skills')"
    :title="t('ai.skillsTab')"
  >
    <template #actions>
      <v-btn :loading="loading" variant="tonal" @click="loadData">
        {{ t('common.refresh') }}
      </v-btn>
    </template>

    <v-card class="page-panel">
      <v-card-text>
        <AISkillsPanel
          :capabilities="skillCapabilities"
          :skills="skills"
        />
      </v-card-text>
    </v-card>
  </PageScaffold>
</template>

<script setup lang="ts">
  import { onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { PageScaffold } from '@/components/workbench'
  import { useAISkillsTab } from '@/composables/useAISkillsTab'
  import AISkillsPanel from '@/views/ai/AISkillsPanel.vue'
  import { useAIPageLoader } from '@/views/ai/pageHelpers'

  const { t } = useI18n()
  const { errorMessage, loading, runPageLoad } = useAIPageLoader(() => t('ai.loadFailed'))

  const {
    capabilities: skillCapabilities,
    loadSkillsData,
    skills,
  } = useAISkillsTab()

  async function loadData () {
    await runPageLoad(loadSkillsData)
  }

  onMounted(() => {
    void loadData()
  })
</script>
