<script setup lang="ts">
import { Brain, RefreshCw, Wrench } from 'lucide-vue-next'
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
import type { WorkbenchMetricItem, WorkbenchTone } from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAISkillsTab } from '@/composables/useAISkillsTab'

const { t } = useI18n()
const errorMessage = ref('')
const search = ref('')
const { capabilities, loadSkillsData, loadingSkills, skills } = useAISkillsTab(t)

const filteredSkills = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) {
    return skills.value
  }
  return skills.value.filter(item => (
    `${item.name} ${item.display_name ?? ''} ${item.description} ${item.display_description ?? ''}`
      .toLowerCase()
      .includes(keyword)
  ))
})
const filteredCapabilities = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) {
    return capabilities.value
  }
  return capabilities.value.filter(item => (
    `${item.capability_name} ${item.description} ${item.origin} ${item.kind}`
      .toLowerCase()
      .includes(keyword)
  ))
})
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: Wrench,
    key: 'skills',
    label: t('ai.skills'),
    value: skills.value.length,
  },
  {
    icon: Brain,
    key: 'capabilities',
    label: t('ai.capabilities'),
    tone: 'info',
    value: capabilities.value.length,
  },
  {
    key: 'readOnly',
    label: t('ai.skillReadOnly'),
    tone: 'success',
    value: skills.value.filter(item => item.read_only).length,
  },
])
const capabilitiesBySkill = computed(() => {
  const map = new Map<string, typeof capabilities.value>()
  for (const item of capabilities.value) {
    const list = map.get(item.capability_name) ?? []
    list.push(item)
    map.set(item.capability_name, list)
  }
  return map
})

async function loadData() {
  errorMessage.value = ''
  try {
    await loadSkillsData()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.loadFailed'))
  }
}

function riskTone(riskLevel: string): WorkbenchTone {
  if (riskLevel === 'low') {
    return 'success'
  }
  if (riskLevel === 'high') {
    return 'error'
  }
  if (riskLevel === 'medium') {
    return 'warning'
  }
  return 'default'
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.skills')"
    :title="t('ai.skillsTab')"
  >
    <template #actions>
      <Button :disabled="loadingSkills" variant="secondary" @click="loadData">
        <RefreshCw :class="{ 'animate-spin': loadingSkills }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" compact />

    <Panel :title="t('ai.skillsTab')">
      <template #actions>
        <Input v-model="search" class="ai-debug-search" :placeholder="t('common.search')" />
      </template>

      <LoadingSkeleton v-if="loadingSkills && skills.length === 0" :rows="6" />
      <EmptyState
        v-else-if="filteredSkills.length === 0"
        :icon="Wrench"
        :title="t('ai.noSkills')"
      />
      <div v-else class="ai-skill-grid">
        <article
          v-for="item in filteredSkills"
          :key="item.name"
          class="ai-skill-card"
        >
          <div class="ai-skill-card__header">
            <div>
              <strong>{{ item.display_name || item.name }}</strong>
              <span>{{ item.name }}</span>
            </div>
            <StatusBadge
              :label="item.risk_label || item.risk_level"
              :tone="riskTone(item.risk_level)"
            />
          </div>
          <p>{{ item.display_description || item.description || t('common.none') }}</p>
          <div class="ai-data-form__meta">
            <Badge :variant="item.read_only ? 'secondary' : 'outline'">
              {{ t('ai.skillReadOnly') }}: {{ item.read_only ? t('ai.enabled') : t('ai.disabled') }}
            </Badge>
            <Badge :variant="item.concurrency_safe ? 'secondary' : 'outline'">
              {{ t('ai.skillConcurrencySafe') }}: {{ item.concurrency_safe ? t('ai.enabled') : t('ai.disabled') }}
            </Badge>
          </div>
          <div class="ai-skill-card__capabilities">
            <span>{{ t('ai.linkedCapabilities') }}</span>
            <div v-if="(capabilitiesBySkill.get(item.name) ?? []).length > 0">
              <Badge
                v-for="capability in capabilitiesBySkill.get(item.name)"
                :key="`${item.name}-${capability.capability_name}`"
                variant="outline"
              >
                {{ capability.capability_name }}
              </Badge>
            </div>
            <p v-else>{{ t('ai.noCapabilities') }}</p>
          </div>
        </article>
      </div>
    </Panel>

    <Panel :title="t('ai.capabilityRegistry')">
      <div class="ai-capability-table">
        <div class="ai-capability-table__head">
          <span>{{ t('ai.capabilityName') }}</span>
          <span>{{ t('ai.skillRiskLevel') }}</span>
          <span>{{ t('ai.executionEnabled') }}</span>
          <span>{{ t('ai.reason') }}</span>
        </div>
        <article
          v-for="item in filteredCapabilities"
          :key="`${item.capability_name}-${item.version}`"
          class="ai-capability-row"
        >
          <div>
            <strong>{{ item.capability_name }}</strong>
            <span>{{ item.description || t('common.none') }}</span>
          </div>
          <StatusBadge :label="item.risk_label || item.risk_level" :tone="riskTone(item.risk_level)" />
          <Badge variant="secondary">{{ item.availability }} / {{ item.policy_status }}</Badge>
          <span>{{ item.diagnostics.join(' / ') || item.origin }}</span>
        </article>
      </div>
    </Panel>
  </PageScaffold>
</template>
