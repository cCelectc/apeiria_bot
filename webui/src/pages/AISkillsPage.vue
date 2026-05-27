<script setup lang="ts">
import { Brain, RefreshCw } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import {
  EmptyState,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
} from '@/components/management'
import type { WorkbenchMetricItem } from '@/components/management'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAISkillsTab } from '@/composables/useAISkillsTab'

const { t } = useI18n()
defineProps<{
  embedded?: boolean
}>()
const errorMessage = ref('')
const search = ref('')
const {
  loadSkillsData,
  loadingSkills,
  reloadSkillsData,
  reloadingSkills,
  skills,
} = useAISkillsTab(t)

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
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: Brain,
    key: 'skills',
    label: t('ai.skills'),
    value: skills.value.length,
  },
])

async function loadData() {
  errorMessage.value = ''
  try {
    await loadSkillsData()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.loadFailed'))
  }
}

async function reloadData() {
  errorMessage.value = ''
  try {
    await reloadSkillsData()
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
    :subtitle="t('ai.pageSubtitle.skills')"
    :title="t('ai.skillsTab')"
  >
    <template #actions>
      <Button :disabled="loadingSkills || reloadingSkills" variant="secondary" @click="loadData">
        <RefreshCw :class="{ 'animate-spin': loadingSkills }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
      <Button :disabled="reloadingSkills" @click="reloadData">
        <RefreshCw :class="{ 'animate-spin': reloadingSkills }" :size="16" />
        {{ t('ai.reloadSkills') }}
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
        :icon="Brain"
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
              :label="item.selectable_now ? t('ai.skillsSelectable') : t('ai.skillsUnavailable')"
              :tone="item.selectable_now ? 'success' : 'warning'"
            />
          </div>
          <p>{{ item.display_description || item.description || t('common.none') }}</p>
          <div class="ai-data-form__meta">
            <Badge variant="outline">{{ item.entry_mode }}</Badge>
            <Badge variant="outline">{{ item.source_path }}</Badge>
            <Badge v-if="item.required_tools.length > 0" variant="secondary">
              {{ item.required_tools.join(', ') }}
            </Badge>
          </div>
          <p v-if="item.error" class="accounts-form-error">{{ item.error }}</p>
        </article>
      </div>
    </Panel>
  </PageScaffold>
</template>
