<script setup lang="ts">
import { Eye, RefreshCw, Wrench } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import {
  EmptyState,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
  StatusBadge,
} from '@/components/management'
import type { WorkbenchMetricItem } from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAIToolsTab } from '@/composables/useAIToolsTab'

const { t } = useI18n()
defineProps<{
  embedded?: boolean
}>()
const errorMessage = ref('')
const search = ref('')
const executionLimit = ref(20)
const { executions, loadToolsData, loadingTools, tools } = useAIToolsTab(t)

const filteredTools = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) {
    return tools.value
  }
  return tools.value.filter(item => (
    `${item.name} ${item.description} ${item.origin} ${item.provider_name}`
      .toLowerCase()
      .includes(keyword)
  ))
})
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: Wrench,
    key: 'tools',
    label: t('ai.tools'),
    value: tools.value.length,
  },
  {
    icon: Eye,
    key: 'executions',
    label: t('ai.debugToolCallCount'),
    value: executions.value.length,
  },
])

async function loadData() {
  errorMessage.value = ''
  try {
    await loadToolsData(executionLimit.value)
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.loadFailed'))
  }
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :embedded="embedded"
    :error-message="errorMessage"
    :subtitle="t('ai.toolsObservationSubtitle')"
    :title="t('ai.toolsTab')"
  >
    <template #actions>
      <Button :disabled="loadingTools" variant="secondary" @click="loadData">
        <RefreshCw :class="{ 'animate-spin': loadingTools }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" compact />

    <Panel :title="t('ai.toolsTab')">
      <template #actions>
        <Input v-model="search" class="ai-debug-search" :placeholder="t('common.search')" />
      </template>

      <LoadingSkeleton v-if="loadingTools && tools.length === 0" :rows="6" />
      <EmptyState
        v-else-if="filteredTools.length === 0"
        :icon="Wrench"
        :title="t('ai.noTools')"
      />
      <div v-else class="ai-skill-grid">
        <article
          v-for="item in filteredTools"
          :key="item.name"
          class="ai-skill-card"
        >
          <div class="ai-skill-card__header">
            <div>
              <strong>{{ item.name }}</strong>
              <span>{{ item.provider_name }}</span>
            </div>
            <StatusBadge
              :label="item.status"
              :tone="item.status === 'visible' ? 'success' : item.status === 'denied' ? 'warning' : 'default'"
            />
          </div>
          <p>{{ item.description || t('common.none') }}</p>
          <div class="ai-data-form__meta">
            <Badge variant="outline">{{ item.origin }}</Badge>
            <Badge variant="outline">{{ item.required_level }}</Badge>
            <Badge variant="outline">{{ item.readiness_code }}</Badge>
          </div>
          <p v-if="item.denied_reason">{{ item.denied_reason }}</p>
          <p v-else-if="item.unavailable_reason">{{ item.unavailable_reason }}</p>
        </article>
      </div>
    </Panel>

    <Panel :title="t('ai.toolExecutionSummary')">
      <template #actions>
        <Input
          v-model="executionLimit"
          class="w-24"
          type="number"
          @change="loadData"
        />
      </template>

      <LoadingSkeleton v-if="loadingTools && executions.length === 0" :rows="5" />
      <EmptyState
        v-else-if="executions.length === 0"
        :icon="Eye"
        :title="t('ai.noPreviewYet')"
      />
      <div v-else class="ai-debug-execution-list">
        <article
          v-for="item in executions"
          :key="item.execution_id"
          class="ai-debug-execution"
        >
          <div>
            <strong>{{ item.tool_name }}</strong>
            <span>{{ item.created_at }}</span>
          </div>
          <StatusBadge :label="item.status" :tone="item.status === 'success' ? 'success' : item.status === 'error' ? 'error' : 'warning'" />
          <div class="ai-data-form__meta">
            <Badge variant="outline">{{ item.session_id }}</Badge>
            <Badge v-if="item.trace_id" variant="outline">{{ item.trace_id }}</Badge>
            <Badge v-if="item.call_id" variant="outline">{{ item.call_id }}</Badge>
          </div>
          <p>{{ item.reason || t('common.none') }}</p>
        </article>
      </div>
    </Panel>
  </PageScaffold>
</template>
