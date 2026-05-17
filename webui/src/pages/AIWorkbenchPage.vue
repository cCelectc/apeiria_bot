<script setup lang="ts">
import type { Component } from 'vue'
import {
  Bot,
  BrainCircuit,
  Bug,
  DatabaseZap,
  MessagesSquare,
  Settings2,
} from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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

type AIWorkbenchArea = 'models' | 'sessions' | 'context' | 'behavior' | 'debug'
type AIContextArea = 'knowledge' | 'memories' | 'relationships' | 'profiles'
type AIBehaviorArea = 'personas' | 'skills' | 'futureTasks'
type WorkbenchAreaOption<T extends string> = {
  description: string
  icon: Component
  label: string
  value: T
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const areas: Array<WorkbenchAreaOption<AIWorkbenchArea>> = [
  { description: 'ai.pageSubtitle.models', icon: Settings2, label: 'ai.modelsTitle', value: 'models' },
  { description: 'ai.pageSubtitle.sessions', icon: MessagesSquare, label: 'ai.sessionsTab', value: 'sessions' },
  { description: 'ai.pageSubtitle.knowledge', icon: DatabaseZap, label: 'ai.workbenchContext', value: 'context' },
  { description: 'ai.pageSubtitle.personas', icon: BrainCircuit, label: 'ai.workbenchBehavior', value: 'behavior' },
  { description: 'ai.pageSubtitle.debug', icon: Bug, label: 'ai.debugTab', value: 'debug' },
]
const contextAreas: Array<WorkbenchAreaOption<AIContextArea>> = [
  { description: 'ai.pageSubtitle.knowledge', icon: DatabaseZap, label: 'ai.knowledgeTab', value: 'knowledge' },
  { description: 'ai.pageSubtitle.memories', icon: DatabaseZap, label: 'ai.memoryTab', value: 'memories' },
  { description: 'ai.pageSubtitle.relationships', icon: DatabaseZap, label: 'ai.relationshipTab', value: 'relationships' },
  { description: 'ai.pageSubtitle.profiles', icon: DatabaseZap, label: 'ai.profileTab', value: 'profiles' },
]
const behaviorAreas: Array<WorkbenchAreaOption<AIBehaviorArea>> = [
  { description: 'ai.pageSubtitle.personas', icon: BrainCircuit, label: 'ai.personasTab', value: 'personas' },
  { description: 'ai.pageSubtitle.skills', icon: BrainCircuit, label: 'ai.skillsTab', value: 'skills' },
  { description: 'ai.pageSubtitle.futureTasks', icon: BrainCircuit, label: 'ai.futureTaskTab', value: 'futureTasks' },
]

const activeAreaMeta = computed(() =>
  areas.find(area => area.value === activeArea.value) ?? areas[0],
)

const activeArea = computed({
  get: () => normalizeArea(route.query.area),
  set: value => {
    updateQuery({ area: normalizeArea(value) })
  },
})
const activeContextArea = computed({
  get: () => normalizeContextArea(route.query.context),
  set: value => {
    updateQuery({ area: 'context', context: normalizeContextArea(value) })
  },
})
const activeBehaviorArea = computed({
  get: () => normalizeBehaviorArea(route.query.behavior),
  set: value => {
    updateQuery({ area: 'behavior', behavior: normalizeBehaviorArea(value) })
  },
})

function updateQuery(next: Record<string, string>) {
  void router.replace({
    query: {
      ...route.query,
      ...next,
    },
  })
}

function normalizeArea(value: unknown): AIWorkbenchArea {
  return ['models', 'sessions', 'context', 'behavior', 'debug'].includes(String(value))
    ? value as AIWorkbenchArea
    : 'models'
}

function normalizeContextArea(value: unknown): AIContextArea {
  return ['knowledge', 'memories', 'relationships', 'profiles'].includes(String(value))
    ? value as AIContextArea
    : 'knowledge'
}

function normalizeBehaviorArea(value: unknown): AIBehaviorArea {
  return ['personas', 'skills', 'futureTasks'].includes(String(value))
    ? value as AIBehaviorArea
    : 'personas'
}
</script>

<template>
  <section class="workbench-hub">
    <Card class="workbench-hub__summary">
      <CardHeader>
        <div class="workbench-hub__summary-title">
          <Bot />
          <div>
            <CardTitle>{{ t('layout.aiWorkbench') }}</CardTitle>
            <CardDescription>{{ t(activeAreaMeta.description) }}</CardDescription>
          </div>
        </div>
        <Badge variant="secondary">
          {{ t(activeAreaMeta.label) }}
        </Badge>
      </CardHeader>
    </Card>

    <Tabs v-model="activeArea" class="workbench-hub__tabs">
      <div class="workbench-hub__bar">
        <TabsList class="workbench-hub__tabs-list">
          <TabsTrigger v-for="area in areas" :key="area.value" :value="area.value">
            {{ t(area.label) }}
          </TabsTrigger>
        </TabsList>
      </div>

      <TabsContent v-if="activeArea === 'models'" value="models">
        <AIModelsPage />
      </TabsContent>

      <TabsContent v-if="activeArea === 'sessions'" value="sessions">
        <AISessionsPage />
      </TabsContent>

      <TabsContent v-if="activeArea === 'context'" value="context">
        <Tabs v-model="activeContextArea" class="workbench-hub__nested-tabs">
          <TabsList class="workbench-hub__nested-tabs-list">
            <TabsTrigger v-for="area in contextAreas" :key="area.value" :value="area.value">
              {{ t(area.label) }}
            </TabsTrigger>
          </TabsList>

          <TabsContent v-if="activeContextArea === 'knowledge'" value="knowledge">
            <AIKnowledgePage />
          </TabsContent>
          <TabsContent v-if="activeContextArea === 'memories'" value="memories">
            <AIMemoriesPage />
          </TabsContent>
          <TabsContent v-if="activeContextArea === 'relationships'" value="relationships">
            <AIRelationshipsPage />
          </TabsContent>
          <TabsContent v-if="activeContextArea === 'profiles'" value="profiles">
            <AIProfilesPage />
          </TabsContent>
        </Tabs>
      </TabsContent>

      <TabsContent v-if="activeArea === 'behavior'" value="behavior">
        <Tabs v-model="activeBehaviorArea" class="workbench-hub__nested-tabs">
          <TabsList class="workbench-hub__nested-tabs-list">
            <TabsTrigger v-for="area in behaviorAreas" :key="area.value" :value="area.value">
              {{ t(area.label) }}
            </TabsTrigger>
          </TabsList>

          <TabsContent v-if="activeBehaviorArea === 'personas'" value="personas">
            <AIPersonasPage />
          </TabsContent>
          <TabsContent v-if="activeBehaviorArea === 'skills'" value="skills">
            <AISkillsPage />
          </TabsContent>
          <TabsContent v-if="activeBehaviorArea === 'futureTasks'" value="futureTasks">
            <AIFutureTasksPage />
          </TabsContent>
        </Tabs>
      </TabsContent>

      <TabsContent v-if="activeArea === 'debug'" value="debug">
        <AIDebugPage />
      </TabsContent>
    </Tabs>
  </section>
</template>
