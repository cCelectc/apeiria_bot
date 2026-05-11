<script setup lang="ts">
import type { WorkbenchMetricItem, WorkbenchTone } from '@/components/management'
import {
  Brain,
  Bug,
  ContactRound,
  MessagesSquare,
  RefreshCw,
  ServerCog,
  Wrench,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  getAIBootstrap,
  getAIModelProfiles,
  getAIPersonas,
  getAIRecentTargets,
  getAISkills,
  getAISourceModels,
  getAISources,
  type AIModelProfileItem,
  type AIPersonaItem,
  type AIRecentTargetItem,
  type AISkillItem,
  type AISourceItem,
  type AISourceModelItem,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import {
  EmptyState,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
  StatusBadge,
} from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useNoticeStore } from '@/stores/notice'
import {
  deriveAISetupWorkflow,
  resolveAISetupActionRoute,
  type AISetupStepState,
} from '@/utils/aiSetupWorkflow'
import { aiManagementPageDescriptors, type AIManagementPage } from '@/router/aiRoutes'

const { t } = useI18n()
const router = useRouter()
const noticeStore = useNoticeStore()

const loading = ref(false)
const errorMessage = ref('')
const bootstrapLoaded = ref(false)
const sources = ref<AISourceItem[]>([])
const sourceModels = ref<AISourceModelItem[]>([])
const modelProfiles = ref<AIModelProfileItem[]>([])
const personas = ref<AIPersonaItem[]>([])
const memories = ref<AIRecentTargetItem[]>([])
const skills = ref<AISkillItem[]>([])

const selectedSource = computed(() =>
  sources.value.find(item => item.capability_type === 'chat_completion')
  || sources.value[0]
  || null,
)
const selectedSourceApiKeys = computed(() => {
  const raw = selectedSource.value?.extra_config?.api_keys
  return Array.isArray(raw)
    ? raw.filter((value): value is string => typeof value === 'string')
    : []
})
const setupWorkflow = computed(() => deriveAISetupWorkflow({
  canFetchSourceModels: Boolean(selectedSource.value),
  canSaveModel: true,
  canSaveProfile: true,
  canSaveSource: true,
  capabilityType: selectedSource.value?.capability_type || 'chat_completion',
  fetchedSourceModelCount: 0,
  modelProfiles: modelProfiles.value,
  selectedSource: selectedSource.value
    ? {
        api_base: selectedSource.value.api_base,
        api_keys: selectedSourceApiKeys.value,
        enabled: selectedSource.value.enabled,
        name: selectedSource.value.name,
        preset_type: selectedSource.value.preset_type,
        source_id: selectedSource.value.source_id,
      }
    : null,
  sourceCount: sources.value.length,
  sourceModels: sourceModels.value,
}))
const overviewStatusTitleKey = computed(() =>
  setupWorkflow.value.status === 'usable'
    ? 'ai.setupUsableTitle'
    : 'ai.setupDegradedTitle',
)
const overviewStatusTextKey = computed(() =>
  setupWorkflow.value.status === 'usable'
    ? 'ai.setupUsableText'
    : `ai.setupDependency.${setupWorkflow.value.dependency}`,
)
const aiMetrics = computed<WorkbenchMetricItem[]>(() => [
  {
    key: 'sources',
    label: t('ai.providersTab'),
    value: sources.value.length,
    icon: ServerCog,
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
    icon: Brain,
    tone: 'info',
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
    icon: MessagesSquare,
  },
  {
    key: 'memories',
    label: t('ai.memoryTab'),
    value: memories.value.length,
    icon: Brain,
    tone: 'warning',
  },
  {
    key: 'profiles',
    label: t('ai.personProfileTab'),
    value: modelProfiles.value.length,
    icon: ContactRound,
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
    icon: Wrench,
  },
])
const overviewDestinations = computed(() => {
  const destinationPages = new Set<AIManagementPage>(
    setupWorkflow.value.status === 'usable'
      ? ['models', 'debug']
      : ['models'],
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

function stepTone(state: AISetupStepState): WorkbenchTone {
  if (state === 'complete') {
    return 'success'
  }
  if (state === 'current') {
    return 'info'
  }
  if (state === 'blocked') {
    return 'error'
  }
  return 'default'
}

async function handleOverviewPrimaryAction() {
  await router.push(resolveAISetupActionRoute(
    setupWorkflow.value.nextAction.kind,
    'chat',
  ))
}

async function openDestination(routeName: string) {
  await router.push({ name: routeName })
}

async function loadData() {
  loading.value = true
  errorMessage.value = ''
  try {
    await getAIBootstrap()
    bootstrapLoaded.value = true
    const [
      sourcesResponse,
      profilesResponse,
      personasResponse,
      memoriesResponse,
      skillsResponse,
    ] = await Promise.all([
      getAISources(),
      getAIModelProfiles(),
      getAIPersonas(),
      getAIRecentTargets({ limit: 20 }),
      getAISkills(),
    ])
    sources.value = sourcesResponse.data
    modelProfiles.value = profilesResponse.data
    personas.value = personasResponse.data
    memories.value = memoriesResponse.data
    skills.value = skillsResponse.data
    sourceModels.value = await loadAllSourceModels(sourcesResponse.data)
  } catch (error) {
    const message = getErrorMessage(error, t('ai.loadFailed'))
    errorMessage.value = message
    noticeStore.show(message, 'error')
  } finally {
    loading.value = false
  }
}

async function loadAllSourceModels(sourceItems: AISourceItem[]) {
  const results = await Promise.allSettled(
    sourceItems.map(item => getAISourceModels(item.source_id)),
  )
  return results.flatMap(result =>
    result.status === 'fulfilled' ? result.value.data : [],
  )
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.overview')"
    :title="t('ai.overviewTitle')"
  >
    <template #actions>
      <Button :disabled="loading" variant="secondary" @click="loadData">
        <RefreshCw :class="{ 'animate-spin': loading }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <LoadingSkeleton v-if="loading && !bootstrapLoaded" rows="8" />

    <div v-else class="ai-overview-page">
      <Panel class="ai-overview-status-panel">
        <div class="ai-overview-status">
          <div class="ai-overview-status__body">
            <StatusBadge
              :label="t(setupWorkflow.status === 'usable' ? 'ai.setupStatusUsable' : 'ai.setupStatusDegraded')"
              :tone="setupWorkflow.status === 'usable' ? 'success' : 'warning'"
            />
            <h2>{{ t(overviewStatusTitleKey) }}</h2>
            <p>{{ t(overviewStatusTextKey) }}</p>
            <div class="ai-overview-status__chips">
              <Badge variant="secondary">
                {{ t('ai.setupProgress', setupWorkflow.progress) }}
              </Badge>
              <Badge v-if="selectedSource" variant="outline">
                {{ selectedSource.name }}
              </Badge>
            </div>
          </div>

          <div class="ai-overview-status__action">
            <span>{{ t('ai.setupNextAction') }}</span>
            <Button @click="handleOverviewPrimaryAction">
              {{ t(`ai.setupAction.${setupWorkflow.nextAction.kind}`) }}
            </Button>
          </div>
        </div>
      </Panel>

      <MetricStrip compact :items="aiMetrics" />

      <Panel>
        <div class="ai-overview-steps">
          <article
            v-for="step in setupWorkflow.steps"
            :key="step.key"
            class="ai-overview-step"
          >
            <StatusBadge
              :label="t(`ai.setupStep.${step.key}`)"
              :tone="stepTone(step.state)"
            />
            <p>{{ t(`ai.modelFlowStepHint.${step.key}`) }}</p>
          </article>
        </div>
      </Panel>

      <div class="ai-overview-destinations">
        <article
          v-for="item in overviewDestinations"
          :key="item.page"
          class="ai-overview-destination"
          :class="{ 'ai-overview-destination--primary': item.primary }"
        >
          <div>
            <h2>{{ item.title }}</h2>
            <p>{{ item.description }}</p>
          </div>
          <Button variant="secondary" @click="openDestination(item.routeName)">
            {{ t('ai.openSubpage') }}
          </Button>
        </article>
      </div>

      <EmptyState
        v-if="overviewDestinations.length === 0"
        :icon="Bug"
        :title="t('ai.redirectingToOverview')"
      />
    </div>
  </PageScaffold>
</template>
