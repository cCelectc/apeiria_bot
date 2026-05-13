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
    label: t('ai.requiredLevel'),
    tone: 'success',
    value: capabilities.value.filter(item => item.required_level === 'read').length,
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

function levelTone(level: string): WorkbenchTone {
  if (level === 'read') {
    return 'success'
  }
  if (level === 'admin' || level === 'host') {
    return 'error'
  }
  if (level === 'write') {
    return 'warning'
  }
  return 'default'
}

function readinessTone(value: string): WorkbenchTone {
  return value === 'ready' ? 'success' : 'warning'
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
              :label="item.name"
              tone="info"
            />
          </div>
          <p>{{ item.display_description || item.description || t('common.none') }}</p>
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
          <span>{{ t('ai.requiredLevel') }}</span>
          <span>{{ t('ai.readiness') }}</span>
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
          <StatusBadge :label="item.required_level" :tone="levelTone(item.required_level)" />
          <StatusBadge :label="item.readiness" :tone="readinessTone(item.readiness)" />
          <span>{{ item.diagnostics.join(' / ') || item.origin }}</span>
        </article>
      </div>
    </Panel>
  </PageScaffold>
</template>
