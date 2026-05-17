<script setup lang="ts">
import { CalendarClock, RefreshCw, Trash2 } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import {
  EmptyState,
  FormField,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
} from '@/components/management'
import type { WorkbenchMetricItem } from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAIFutureTasksTab } from '@/composables/useAIFutureTasksTab'

const { t } = useI18n()
const errorMessage = ref('')
const {
  cancelFutureTask,
  cancellingTaskId,
  futureTaskForm,
  futureTasks,
  loadFutureTasks,
  loadingFutureTasks,
} = useAIFutureTasksTab(t)
const limitOptions = [10, 20, 50, 100]
const activeTaskCount = computed(() => (
  futureTasks.value.filter(item => !['cancelled', 'completed', 'failed'].includes(item.status)).length
))
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: CalendarClock,
    key: 'tasks',
    label: t('ai.futureTaskTab'),
    value: futureTasks.value.length,
  },
  {
    key: 'active',
    label: t('ai.enabled'),
    tone: activeTaskCount.value > 0 ? 'info' : 'default',
    value: activeTaskCount.value,
  },
  {
    key: 'failed',
    label: t('ai.toolStatusError'),
    tone: 'error',
    value: futureTasks.value.filter(item => item.status === 'failed').length,
  },
])

async function loadData() {
  errorMessage.value = ''
  try {
    await loadFutureTasks()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.futureTaskLoadFailed'))
  }
}

function canCancelStatus(status: string) {
  return !['cancelled', 'completed'].includes(status)
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.futureTasks')"
    :title="t('ai.futureTaskTab')"
  >
    <template #actions>
      <Button :disabled="loadingFutureTasks" variant="secondary" @click="loadData">
        <RefreshCw :class="{ 'animate-spin': loadingFutureTasks }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" compact />

    <Panel :title="t('ai.futureTaskTab')">
      <template #actions>
        <FormField :label="t('ai.futureTaskLimit')">
          <Select v-model="futureTaskForm.limit" @update:model-value="loadFutureTasks">
            <SelectTrigger class="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="option in limitOptions"
                  :key="option"
                  :value="option"
                >
                  {{ option }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </FormField>
      </template>

      <LoadingSkeleton v-if="loadingFutureTasks && futureTasks.length === 0" :rows="5" />
      <EmptyState
        v-else-if="futureTasks.length === 0"
        :icon="CalendarClock"
        :title="t('ai.futureTaskTab')"
        :text="t('ai.noPreviewYet')"
      />
      <div v-else class="ai-task-list">
        <article
          v-for="item in futureTasks"
          :key="item.task_id"
          class="ai-task-row"
        >
          <div class="ai-task-row__main">
            <div class="ai-task-row__title">
              <strong>{{ item.title || item.task_id }}</strong>
              <Badge variant="secondary">{{ item.status }}</Badge>
            </div>
            <p>{{ item.description || t('common.none') }}</p>
            <div class="ai-task-row__meta">
              <span>{{ t('ai.futureTaskTriggerAt') }}: {{ item.trigger_at }}</span>
              <span>{{ item.platform }} / {{ item.scene_type }} / {{ item.scene_id }}</span>
              <span v-if="item.user_id">{{ t('ai.relationshipUserId') }}: {{ item.user_id }}</span>
              <span v-if="item.last_error">{{ item.last_error }}</span>
            </div>
          </div>
          <Button
            :disabled="!canCancelStatus(item.status) || cancellingTaskId === item.task_id"
            size="sm"
            variant="destructive"
            @click="cancelFutureTask(item.task_id)"
          >
            <RefreshCw
              v-if="cancellingTaskId === item.task_id"
              class="animate-spin"
              :size="15"
            />
            <Trash2 v-else :size="15" />
            {{ t('common.cancel') }}
          </Button>
        </article>
      </div>
    </Panel>
  </PageScaffold>
</template>
