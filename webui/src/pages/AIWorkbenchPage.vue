<script setup lang="ts">
import type { Component } from 'vue'
import {
  BrainCircuit,
  Bug,
  CalendarClock,
  ContactRound,
  DatabaseZap,
  MessagesSquare,
  Network,
  Settings2,
  Wrench,
} from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { PageScaffold } from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  buildAIWorkbenchAreaQuery,
  normalizeAIWorkbenchRouteState,
  type AIWorkbenchRouteArea,
} from '@/utils/aiRouteState'
import AIDebugPage from './AIDebugPage.vue'
import AIFutureTasksPage from './AIFutureTasksPage.vue'
import AIKnowledgePage from './AIKnowledgePage.vue'
import AIMemoriesPage from './AIMemoriesPage.vue'
import AIModelsPage from './AIModelsPage.vue'
import AIPersonasPage from './AIPersonasPage.vue'
import AIProfilesPage from './AIProfilesPage.vue'
import AIRelationshipsPage from './AIRelationshipsPage.vue'
import AISessionsPage from './AISessionsPage.vue'
import AISkillsPage from './AISkillsPage.vue'

type WorkbenchAreaOption = {
  description: string
  group: 'connection' | 'runtime' | 'context' | 'behavior'
  icon: Component
  label: string
  value: AIWorkbenchRouteArea
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const areas: WorkbenchAreaOption[] = [
  {
    description: 'ai.pageSubtitle.models',
    group: 'connection',
    icon: Settings2,
    label: 'ai.modelsTitle',
    value: 'models',
  },
  {
    description: 'ai.pageSubtitle.sessions',
    group: 'runtime',
    icon: MessagesSquare,
    label: 'ai.sessionsTab',
    value: 'sessions',
  },
  {
    description: 'ai.pageSubtitle.debug',
    group: 'runtime',
    icon: Bug,
    label: 'ai.debugTab',
    value: 'debug',
  },
  {
    description: 'ai.pageSubtitle.knowledge',
    group: 'context',
    icon: DatabaseZap,
    label: 'ai.knowledgeTab',
    value: 'knowledge',
  },
  {
    description: 'ai.pageSubtitle.memories',
    group: 'context',
    icon: BrainCircuit,
    label: 'ai.memoryTab',
    value: 'memories',
  },
  {
    description: 'ai.pageSubtitle.relationships',
    group: 'context',
    icon: Network,
    label: 'ai.relationshipTab',
    value: 'relationships',
  },
  {
    description: 'ai.pageSubtitle.profiles',
    group: 'context',
    icon: ContactRound,
    label: 'ai.profileTab',
    value: 'profiles',
  },
  {
    description: 'ai.pageSubtitle.personas',
    group: 'behavior',
    icon: BrainCircuit,
    label: 'ai.personasTab',
    value: 'personas',
  },
  {
    description: 'ai.pageSubtitle.skills',
    group: 'behavior',
    icon: Wrench,
    label: 'ai.skillsTab',
    value: 'skills',
  },
  {
    description: 'ai.pageSubtitle.futureTasks',
    group: 'behavior',
    icon: CalendarClock,
    label: 'ai.futureTaskTab',
    value: 'futureTasks',
  },
]

const routeState = computed(() => normalizeAIWorkbenchRouteState(route.query))
const activeArea = computed(() => routeState.value.area)
const activeAreaMeta = computed(() => (
  areas.find(area => area.value === activeArea.value) ?? areas[0]
))
const groupedAreas = computed(() => [
  { key: 'connection', label: t('ai.workbenchGroup.connection') },
  { key: 'runtime', label: t('ai.workbenchGroup.runtime') },
  { key: 'context', label: t('ai.workbenchGroup.context') },
  { key: 'behavior', label: t('ai.workbenchGroup.behavior') },
].map(group => ({
  ...group,
  areas: areas.filter(area => area.group === group.key),
})))
const activeGroup = computed(() => activeAreaMeta.value.group)

function setActiveArea(value: AIWorkbenchRouteArea) {
  if (value === activeArea.value) {
    return
  }
  void router.replace({
    query: buildAIWorkbenchAreaQuery(value, route.query),
  })
}
</script>

<template>
  <PageScaffold
    dense
    :subtitle="t(activeAreaMeta.description)"
    :title="t(activeAreaMeta.label)"
  >
    <template #actions>
      <Badge variant="secondary">
        {{ t('layout.aiWorkbench') }}
      </Badge>
    </template>

    <template #before>
      <nav class="ai-workbench-frame" :aria-label="t('layout.aiWorkbench')">
        <section
          v-for="group in groupedAreas"
          :key="group.key"
          class="ai-workbench-frame__group"
          :class="{ 'ai-workbench-frame__group--active': activeGroup === group.key }"
        >
          <span class="ai-workbench-frame__label">{{ group.label }}</span>
          <div class="ai-workbench-frame__items">
            <Button
              v-for="area in group.areas"
              :key="area.value"
              :aria-current="activeArea === area.value ? 'page' : undefined"
              :variant="activeArea === area.value ? 'default' : 'ghost'"
              size="sm"
              @click="setActiveArea(area.value)"
            >
              <component :is="area.icon" :size="15" />
              {{ t(area.label) }}
            </Button>
          </div>
        </section>
      </nav>
    </template>

    <AIModelsPage v-if="activeArea === 'models'" embedded />
    <AISessionsPage v-else-if="activeArea === 'sessions'" embedded />
    <AIDebugPage v-else-if="activeArea === 'debug'" embedded />
    <AIKnowledgePage v-else-if="activeArea === 'knowledge'" embedded />
    <AIMemoriesPage v-else-if="activeArea === 'memories'" embedded />
    <AIRelationshipsPage v-else-if="activeArea === 'relationships'" embedded />
    <AIProfilesPage v-else-if="activeArea === 'profiles'" embedded />
    <AIPersonasPage v-else-if="activeArea === 'personas'" embedded />
    <AISkillsPage v-else-if="activeArea === 'skills'" embedded />
    <AIFutureTasksPage v-else embedded />
  </PageScaffold>
</template>
