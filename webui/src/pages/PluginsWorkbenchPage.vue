<script setup lang="ts">
import type { Component } from 'vue'
import { PackageCheck, Plug, SlidersHorizontal, Store } from 'lucide-vue-next'
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
import PluginLoadingRulesPage from './PluginLoadingRulesPage.vue'
import PluginsPage from './PluginsPage.vue'
import PluginStorePage from './PluginStorePage.vue'

type PluginWorkbenchArea = 'installed' | 'store' | 'rules'
type PluginAreaOption = {
  description: string
  icon: Component
  label: string
  value: PluginWorkbenchArea
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const areas: PluginAreaOption[] = [
  {
    description: 'plugins.directConfigDescription',
    icon: PackageCheck,
    label: 'plugins.installedTab',
    value: 'installed',
  },
  {
    description: 'pluginStore.description',
    icon: Store,
    label: 'pluginStore.title',
    value: 'store',
  },
  {
    description: 'plugins.configDescription',
    icon: SlidersHorizontal,
    label: 'plugins.configTitle',
    value: 'rules',
  },
]

const activeArea = computed({
  get: () => normalizeArea(route.query.area),
  set: value => {
    void router.replace({
      query: {
        ...route.query,
        area: normalizeArea(value),
      },
    })
  },
})

function normalizeArea(value: unknown): PluginWorkbenchArea {
  const area = String(value)
  return area === 'store' || area === 'rules' ? area : 'installed'
}

const activeAreaMeta = computed(() =>
  areas.find(area => area.value === activeArea.value) ?? areas[0],
)
</script>

<template>
  <section class="workbench-hub">
    <Card class="workbench-hub__summary">
      <CardHeader>
        <div class="workbench-hub__summary-title">
          <Plug />
          <div>
            <CardTitle>{{ t('plugins.workbenchTitle') }}</CardTitle>
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

      <TabsContent v-if="activeArea === 'installed'" value="installed">
        <PluginsPage />
      </TabsContent>

      <TabsContent v-if="activeArea === 'store'" value="store">
        <PluginStorePage />
      </TabsContent>

      <TabsContent v-if="activeArea === 'rules'" value="rules">
        <PluginLoadingRulesPage />
      </TabsContent>
    </Tabs>
  </section>
</template>
