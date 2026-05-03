<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.overview')"
    :title="t('ai.overviewTitle')"
  >
    <template #actions>
      <v-btn :loading="loading" variant="tonal" @click="loadData">
        {{ t('common.refresh') }}
      </v-btn>
    </template>

    <div class="ai-overview-page">
      <v-sheet class="ai-overview-status">
        <div class="ai-overview-status__body">
          <v-chip
            :color="setupWorkflow.status === 'usable' ? 'success' : 'warning'"
            size="small"
            variant="tonal"
          >
            {{ t(setupWorkflow.status === 'usable' ? 'ai.setupStatusUsable' : 'ai.setupStatusDegraded') }}
          </v-chip>
          <div class="ai-overview-status__title">
            {{ t(overviewStatusTitleKey) }}
          </div>
          <div class="ai-overview-status__text">
            {{ t(overviewStatusTextKey) }}
          </div>
        </div>
        <div class="ai-overview-status__action">
          <div class="ai-overview-status__label">
            {{ t('ai.setupNextAction') }}
          </div>
          <v-btn
            color="primary"
            prepend-icon="mdi-arrow-right"
            @click="handleOverviewPrimaryAction(setupWorkflow.nextAction.kind)"
          >
            {{ t(`ai.setupAction.${setupWorkflow.nextAction.kind}`) }}
          </v-btn>
        </div>
      </v-sheet>

      <MetricStrip compact :items="aiMetrics" />

      <div class="ai-overview-destinations">
        <v-sheet
          v-for="item in overviewDestinations"
          :key="item.page"
          class="ai-overview-destination"
          :class="{ 'ai-overview-destination--primary': item.primary }"
        >
          <div class="ai-overview-destination__body">
            <v-icon :icon="item.icon" size="22" />
            <div>
              <div class="ai-overview-destination__title">
                {{ item.title }}
              </div>
              <div class="ai-overview-destination__text">
                {{ item.description }}
              </div>
            </div>
          </div>
          <v-btn
            color="primary"
            :to="{ name: item.routeName }"
            variant="tonal"
          >
            {{ t('ai.openSubpage') }}
          </v-btn>
        </v-sheet>
      </div>
    </div>
  </PageScaffold>
</template>

<script setup lang="ts">
  import type { WorkbenchMetricItem } from '@/components/workbench'
  import type { AISetupNextActionKind } from '@/composables/aiModels/setupWorkflow'
  import type { AISourceCapabilityRouteValue } from '@/views/ai/routeState'
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { MetricStrip, PageScaffold } from '@/components/workbench'
  import { useAIMemoryTab } from '@/composables/useAIMemoryTab'
  import { useAIModelsTab } from '@/composables/useAIModelsTab'
  import { useAIPersonasTab } from '@/composables/useAIPersonasTab'
  import { useAIPersonProfilesTab } from '@/composables/useAIPersonProfilesTab'
  import { useAISkillsTab } from '@/composables/useAISkillsTab'
  import { resolveAIOverviewDestinationPages } from '@/views/ai/overviewState'
  import { useAIPageLoader } from '@/views/ai/pageHelpers'
  import {
    aiManagementPageDescriptors,
    resolveAISetupActionRoute,
  } from '@/views/ai/routeState'

  const { t } = useI18n()
  const router = useRouter()
  const sourceCapabilityTab = ref<AISourceCapabilityRouteValue>('chat')
  const { errorMessage, loading, runPageLoad } = useAIPageLoader(() => t('ai.loadFailed'))

  const {
    loadModelsData,
    setupWorkflow,
    sourceModels,
    sources,
  } = useAIModelsTab(sourceCapabilityTab, t)

  const {
    loadPersonasData,
    personas,
  } = useAIPersonasTab(t)

  const {
    loadRecentTargets,
    memories,
  } = useAIMemoryTab(t)

  const {
    loadProfiles: loadPersonProfiles,
    profiles: personProfiles,
  } = useAIPersonProfilesTab(t)

  const {
    loadSkillsData,
    skills,
  } = useAISkillsTab()

  const overviewStatusTitleKey = computed(() => (
    setupWorkflow.value.status === 'usable'
      ? 'ai.setupUsableTitle'
      : 'ai.setupDegradedTitle'
  ))
  const overviewStatusTextKey = computed(() => (
    setupWorkflow.value.status === 'usable'
      ? 'ai.setupUsableText'
      : `ai.setupDependency.${setupWorkflow.value.dependency}`
  ))
  const aiMetrics = computed<WorkbenchMetricItem[]>(() => [
    {
      key: 'sources',
      label: t('ai.providersTab'),
      value: sources.value.length,
      icon: 'mdi-server-network',
      hint: t(
        setupWorkflow.value.dependency === 'provider'
          ? 'ai.setupMetricProviderMissing'
          : 'ai.setupMetricProviderReady',
      ),
    },
    {
      key: 'models',
      label: t('ai.sourceModelsTitle'),
      value: sourceModels.value.length,
      icon: 'mdi-cube-outline',
      color: 'info',
      hint: t(
        setupWorkflow.value.dependency === 'model'
          ? 'ai.setupMetricModelMissing'
          : 'ai.setupMetricModelReady',
      ),
    },
    {
      key: 'personas',
      label: t('ai.personasTab'),
      value: personas.value.length,
      icon: 'mdi-account-voice',
    },
    {
      key: 'memories',
      label: t('ai.memoryTab'),
      value: memories.value.length,
      icon: 'mdi-brain',
      color: 'warning',
    },
    {
      key: 'profiles',
      label: t('ai.personProfileTab'),
      value: personProfiles.value.length,
      icon: 'mdi-account-box-outline',
      hint: t(
        setupWorkflow.value.dependency === 'profile'
          ? 'ai.setupMetricProfileMissing'
          : 'ai.setupMetricProfileReady',
      ),
    },
    {
      key: 'skills',
      label: t('ai.skillsTab'),
      value: skills.value.length,
      icon: 'mdi-tools',
    },
  ])
  const overviewDestinations = computed(() => {
    const destinationPages = new Set(
      resolveAIOverviewDestinationPages(setupWorkflow.value.status),
    )
    return aiManagementPageDescriptors
      .filter(item => destinationPages.has(item.page))
      .map(item => ({
        ...item,
        description: t(`ai.overviewDestination.${item.page}`),
        primary: item.page === 'models',
        title: t(item.titleKey),
      }))
  })

  async function handleOverviewPrimaryAction (kind: AISetupNextActionKind) {
    await router.push(resolveAISetupActionRoute(kind, sourceCapabilityTab.value))
  }

  async function loadData () {
    await runPageLoad(async () => {
      await Promise.all([
        loadModelsData(),
        loadPersonasData(),
        loadSkillsData(),
        loadRecentTargets(),
        loadPersonProfiles(),
      ])
    })
  }

  onMounted(() => {
    void loadData()
  })
</script>

<style scoped>
.ai-overview-page {
  display: grid;
  gap: 16px;
}

.ai-overview-status {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
  padding: 18px;
  border: 1px solid rgba(var(--v-theme-outline-variant), 0.32);
  border-radius: var(--shape-large);
  background: rgba(var(--v-theme-surface-container), 0.82);
}

.ai-overview-status__body {
  min-width: 0;
}

.ai-overview-status__title {
  margin-top: 10px;
  color: rgb(var(--v-theme-on-surface));
  font-size: 1.1rem;
  font-weight: 720;
  line-height: 1.35;
}

.ai-overview-status__text {
  max-width: 68ch;
  margin-top: 6px;
  color: rgba(var(--v-theme-on-surface), 0.66);
  font-size: 0.92rem;
  line-height: 1.58;
}

.ai-overview-status__action {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-end;
}

.ai-overview-status__label {
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 0.78rem;
  font-weight: 650;
  line-height: 1.4;
}

.ai-overview-destinations {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.ai-overview-destination {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border: 1px solid rgba(var(--v-theme-outline-variant), 0.28);
  border-radius: var(--shape-large);
  background: rgba(var(--v-theme-surface-container), 0.78);
}

.ai-overview-destination--primary {
  border-color: rgba(var(--v-theme-primary), 0.34);
  background: rgba(var(--v-theme-primary), 0.06);
}

.ai-overview-destination__body {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 12px;
}

.ai-overview-destination__title {
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.98rem;
  font-weight: 700;
  line-height: 1.35;
}

.ai-overview-destination__text {
  margin-top: 4px;
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-size: 0.86rem;
  line-height: 1.5;
}

@media (max-width: 640px) {
  .ai-overview-status {
    grid-template-columns: 1fr;
  }

  .ai-overview-status__action {
    align-items: stretch;
  }

  .ai-overview-destination {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
