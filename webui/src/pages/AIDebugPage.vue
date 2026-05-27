<script setup lang="ts">
import type { AIDebugRouteValue } from '@/utils/aiRouteState'
import {
  Bug,
  CalendarClock,
  MessageSquare,
  RefreshCw,
  Search,
  Trash2,
} from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { getErrorMessage } from '@/api/client'
import {
  EmptyState,
  FormField,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
  SelectableList,
  SelectableListItem,
  SplitPane,
  StatusBadge,
} from '@/components/management'
import type { WorkbenchMetricItem, WorkbenchTone } from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent } from '@/components/ui/tabs'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useAIDebugTab } from '@/composables/useAIDebugTab'
import { useAIFutureTasksTab } from '@/composables/useAIFutureTasksTab'
import { normalizeAIDebugRouteValue } from '@/utils/aiRouteState'

const { t } = useI18n()
defineProps<{
  embedded?: boolean
}>()
const route = useRoute()
const router = useRouter()
const errorMessage = ref('')
const debugTab = ref<AIDebugRouteValue>('conversations')
let applyingRouteState = false

const {
  conversations,
  debugForm,
  latestAssistantTurn,
  loadConversationDetails,
  loadDebugData,
  loadTraces,
  loadingDebug,
  loadingTraces,
  loadingTurns,
  planningPromptChannelSections,
  promptPreview,
  roleplayPromptChannelSections,
  selectedConversation,
  selectedConversationId,
  summarizeRawPayload,
  traceFilter,
  traceIds,
  traces,
  turns,
  usageByResponseSource,
} = useAIDebugTab(t)
const {
  cancelFutureTask,
  cancellingTaskId,
  futureTaskForm,
  futureTasks,
  loadFutureTasks,
  loadingFutureTasks,
} = useAIFutureTasksTab(t)

const limitOptions = [10, 20, 50, 100]
const turnLimitOptions = [20, 50, 100, 200]
const traceStatusOptions = ['__all__', 'success', 'failed', 'skipped']
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: MessageSquare,
    key: 'scenes',
    label: t('ai.debugConversationTitle'),
    value: conversations.value.length,
  },
  {
    key: 'turns',
    label: t('ai.debugMessageCount'),
    tone: 'info',
    value: turns.value.length,
  },
  {
    icon: CalendarClock,
    key: 'future',
    label: t('ai.futureTaskTab'),
    value: futureTasks.value.length,
  },
])
const promptSections = computed(() => [
  ...planningPromptChannelSections.value.map(section => ({
    ...section,
    group: t('ai.promptPreviewPlanning'),
  })),
  ...roleplayPromptChannelSections.value.map(section => ({
    ...section,
    group: t('ai.promptPreviewRoleplay'),
  })),
])

function applyRouteState() {
  const nextTab = normalizeAIDebugRouteValue(route.query.debug)
  if (debugTab.value === nextTab) {
    applyRouteFilters()
    return
  }
  applyingRouteState = true
  debugTab.value = nextTab
  applyingRouteState = false
  applyRouteFilters()
}

function syncRouteQuery() {
  if (route.query.debug === debugTab.value) {
    return
  }
  void router.replace({ query: { ...route.query, debug: debugTab.value } })
}

function applyRouteFilters() {
  const sessionId = routeQueryString(route.query.session)
  const traceId = routeQueryString(route.query.trace)
  if (sessionId) {
    selectedConversationId.value = sessionId
    traceFilter.session_id = sessionId
  }
  if (traceId) {
    traceFilter.trace_id = traceId
  }
}

async function loadData() {
  errorMessage.value = ''
  try {
    await Promise.all([
      loadDebugData(),
      loadFutureTasks(),
    ])
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.loadFailed'))
  }
}

function statusTone(value: string): WorkbenchTone {
  if (['success', 'completed', 'committed', 'delivered'].includes(value)) {
    return 'success'
  }
  if (['error', 'failed', 'timeout'].includes(value)) {
    return 'error'
  }
  if (['pending', 'running'].includes(value)) {
    return 'info'
  }
  return 'default'
}

function canCancelFutureTask(status: string) {
  return !['cancelled', 'completed'].includes(status)
}

function formatJson(value: unknown) {
  if (value == null) {
    return t('common.none')
  }
  return JSON.stringify(value, null, 2)
}

function tokenLabel(value: number | null | undefined) {
  return value == null ? t('common.none') : value.toLocaleString()
}

function usageStatus(trace: { usage: { usage_available: boolean, missing_usage_count: number } }) {
  if (trace.usage.usage_available) {
    return t('ai.usageMeasured')
  }
  return trace.usage.missing_usage_count > 0
    ? t('ai.usageMissing')
    : t('ai.usageNoData')
}

function usageTone(trace: { usage: { usage_available: boolean, missing_usage_count: number } }): WorkbenchTone {
  if (trace.usage.usage_available) {
    return trace.usage.missing_usage_count > 0 ? 'warning' : 'success'
  }
  return trace.usage.missing_usage_count > 0 ? 'warning' : 'default'
}

function routeQueryString(value: unknown) {
  return typeof value === 'string' ? value : ''
}

applyRouteState()

onMounted(() => {
  applyRouteState()
  void loadData()
})

watch(() => route.query.debug, applyRouteState)
watch(debugTab, () => {
  if (!applyingRouteState) {
    syncRouteQuery()
  }
}, { flush: 'sync' })
</script>

<template>
  <PageScaffold
    :embedded="embedded"
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.debug')"
    :title="t('ai.debugTab')"
  >
    <template #actions>
      <Button :disabled="loadingDebug || loadingFutureTasks" variant="secondary" @click="loadData">
        <RefreshCw
          :class="{ 'animate-spin': loadingDebug || loadingFutureTasks }"
          :size="16"
        />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" compact />

    <div class="ai-debug-mode-row">
      <ToggleGroup
        v-model="debugTab"
        :aria-label="t('ai.debugTab')"
        size="sm"
        type="single"
        variant="outline"
      >
        <ToggleGroupItem value="conversations">{{ t('ai.debugConversationTitle') }}</ToggleGroupItem>
        <ToggleGroupItem value="futureTasks">{{ t('ai.futureTaskTab') }}</ToggleGroupItem>
      </ToggleGroup>
    </div>

    <Tabs v-model="debugTab" class="ai-debug-tabs">
      <TabsContent value="conversations">
        <SplitPane wide-sidebar>
          <template #sidebar>
            <Panel :title="t('ai.debugConversationTitle')">
              <template #actions>
                <Select v-model="debugForm.limit" @update:model-value="loadDebugData">
                  <SelectTrigger class="w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem v-for="option in limitOptions" :key="option" :value="option">
                        {{ option }}
                      </SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </template>
              <LoadingSkeleton v-if="loadingDebug && conversations.length === 0" :rows="5" />
              <EmptyState
                v-else-if="conversations.length === 0"
                :icon="MessageSquare"
                :text="t('ai.noConversationSelectedHint')"
                :title="t('ai.noConversationSelected')"
              />
              <SelectableList v-else>
                <SelectableListItem
                  v-for="item in conversations"
                  :key="item.session_id"
                  :active="selectedConversationId === item.session_id"
                  @click="loadConversationDetails(item.session_id)"
                >
                  <div class="ai-data-list-item">
                    <div class="ai-data-list-item__main">
                      <strong>{{ item.summary_text || item.scene_id }}</strong>
                      <span>{{ item.platform }} / {{ item.scene_type }} / {{ item.last_message_at }}</span>
                    </div>
                    <Badge variant="secondary">{{ item.bot_id }}</Badge>
                  </div>
                </SelectableListItem>
              </SelectableList>
            </Panel>
          </template>

          <div class="ai-data-stack">
            <Panel
              :subtitle="selectedConversation?.scene_id || t('ai.noConversationSelectedHint')"
              :title="t('ai.workbenchSelectedConversation')"
            >
              <template #actions>
                <Select v-model="debugForm.turnLimit">
                  <SelectTrigger class="w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem v-for="option in turnLimitOptions" :key="option" :value="option">
                        {{ option }}
                      </SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <Button
                  :disabled="!selectedConversationId || loadingTurns"
                  size="sm"
                  variant="secondary"
                  @click="loadConversationDetails(selectedConversationId)"
                >
                  <RefreshCw :class="{ 'animate-spin': loadingTurns }" :size="15" />
                  {{ t('common.refresh') }}
                </Button>
              </template>

              <div v-if="selectedConversation" class="ai-data-form__meta">
                <Badge variant="secondary">{{ t('ai.conversationId') }}: {{ selectedConversation.session_id }}</Badge>
                <Badge variant="outline">{{ t('ai.lastActiveAt') }}: {{ selectedConversation.last_message_at }}</Badge>
                <Badge variant="outline">{{ t('ai.traceIds') }}: {{ traceIds.length }}</Badge>
              </div>
              <EmptyState
                v-else
                :icon="MessageSquare"
                :text="t('ai.noConversationSelectedHint')"
                :title="t('ai.noConversationSelected')"
              />
            </Panel>

            <Panel :title="t('ai.finalReplyTitle')">
              <EmptyState
                v-if="!latestAssistantTurn"
                :icon="MessageSquare"
                :title="t('common.noData')"
              />
              <article v-else class="ai-debug-turn ai-debug-turn--assistant">
                <div class="ai-debug-turn__meta">
                  <Badge variant="secondary">{{ latestAssistantTurn.model_name || t('common.none') }}</Badge>
                  <Badge variant="outline">{{ latestAssistantTurn.trace_id || t('common.none') }}</Badge>
                </div>
                <p>{{ latestAssistantTurn.text_content }}</p>
              </article>
            </Panel>

            <Panel :title="t('ai.turnContent')">
              <LoadingSkeleton v-if="loadingTurns" :rows="5" />
              <EmptyState v-else-if="turns.length === 0" :icon="MessageSquare" :title="t('common.noData')" />
              <div v-else class="ai-debug-turn-list">
                <article
                  v-for="turn in turns"
                  :key="turn.message_id"
                  class="ai-debug-turn"
                >
                  <div class="ai-debug-turn__meta">
                    <Badge variant="secondary">{{ turn.author_role }}</Badge>
                    <Badge variant="outline">{{ turn.created_at }}</Badge>
                    <Badge v-if="turn.trace_id" variant="outline">{{ turn.trace_id }}</Badge>
                  </div>
                  <p>{{ turn.text_content || summarizeRawPayload(turn.raw_data) }}</p>
                </article>
              </div>
            </Panel>

            <Panel :title="t('ai.promptPreviewTitle')">
              <div v-if="promptPreview" class="ai-data-form__meta">
                <Badge variant="secondary">{{ t('ai.planningModel') }}: {{ promptPreview.planning_model_name || t('common.none') }}</Badge>
                <Badge variant="secondary">{{ t('ai.roleplayModel') }}: {{ promptPreview.roleplay_model_name || t('common.none') }}</Badge>
                <Badge variant="outline">{{ t('ai.memoryHits') }}: {{ promptPreview.memories.length }}</Badge>
              </div>
              <EmptyState
                v-if="!promptPreview"
                :icon="Bug"
                :title="t('ai.noPromptPreview')"
              />
              <div v-else class="ai-prompt-section-list">
                <article
                  v-for="section in promptSections"
                  :key="`${section.group}-${section.key}`"
                  class="ai-prompt-section"
                >
                  <div>
                    <strong>{{ section.group }} / {{ section.title }}</strong>
                    <Badge variant="outline">{{ section.lines.length }}</Badge>
                  </div>
                  <pre>{{ section.lines.join('\n\n') }}</pre>
                </article>
              </div>
            </Panel>

            <Panel :title="t('ai.traceIds')">
              <template #actions>
                <Input v-model="traceFilter.trace_id" class="ai-debug-search" :placeholder="t('ai.traceId')" />
                <Button :disabled="loadingTraces" size="sm" variant="secondary" @click="loadTraces">
                  <Search :size="15" />
                  {{ t('common.search') }}
                </Button>
              </template>
              <div class="ai-debug-trace-filter">
                <FormField :label="t('ai.conversationId')">
                  <Input v-model="traceFilter.session_id" />
                </FormField>
                <FormField :label="t('ai.toolStatus')">
                  <Select v-model="traceFilter.terminal_status">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem v-for="option in traceStatusOptions" :key="option" :value="option">
                          {{ option === '__all__' ? t('common.all') : option }}
                        </SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </FormField>
              </div>
              <div v-if="usageByResponseSource.length > 0" class="ai-usage-breakdown">
                <article
                  v-for="item in usageByResponseSource"
                  :key="item.group_key"
                  class="ai-usage-breakdown__item"
                >
                  <strong>{{ item.group_key }}</strong>
                  <span>{{ t('ai.usageTotalTokens') }}: {{ tokenLabel(item.total_tokens) }}</span>
                  <span>{{ t('ai.usageMissing') }}: {{ item.missing_usage_count }}</span>
                </article>
              </div>
              <LoadingSkeleton v-if="loadingTraces" :rows="4" />
              <div v-else class="ai-debug-trace-list">
                <article
                  v-for="trace in traces"
                  :key="trace.trace_id"
                  class="ai-debug-trace"
                >
                  <div class="ai-debug-turn__meta">
                    <Badge variant="secondary">{{ trace.trace_id }}</Badge>
                    <StatusBadge :label="trace.terminal_status" :tone="statusTone(trace.terminal_status)" />
                    <Badge variant="outline">{{ trace.runtime_mode }}</Badge>
                    <StatusBadge :label="usageStatus(trace)" :tone="usageTone(trace)" />
                    <Badge variant="outline">{{ t('ai.usageTotalTokens') }}: {{ tokenLabel(trace.usage.total_tokens) }}</Badge>
                    <Badge variant="outline">{{ t('ai.usageCalls') }}: {{ trace.usage.call_count }}</Badge>
                  </div>
                  <p>{{ trace.strategy_action }} / {{ trace.strategy_reason_codes.join(', ') || t('common.none') }}</p>
                  <div v-if="trace.usage_events.length > 0" class="ai-debug-trace__usage-events">
                    <span
                      v-for="event in trace.usage_events"
                      :key="event.usage_event_id"
                    >
                      {{ event.response_source }} #{{ event.attempt_index }}:
                      {{ event.usage_available ? tokenLabel(event.total_tokens) : t('ai.usageMissing') }}
                    </span>
                  </div>
                  <pre>{{ formatJson(trace.diagnostics) }}</pre>
                </article>
              </div>
            </Panel>
          </div>
        </SplitPane>
      </TabsContent>

      <TabsContent value="futureTasks">
        <Panel :title="t('ai.futureTaskTab')">
          <template #actions>
            <Select v-model="futureTaskForm.limit" @update:model-value="loadFutureTasks">
              <SelectTrigger class="w-28"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem v-for="option in limitOptions" :key="option" :value="option">
                    {{ option }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </template>
          <LoadingSkeleton v-if="loadingFutureTasks && futureTasks.length === 0" :rows="5" />
          <EmptyState
            v-else-if="futureTasks.length === 0"
            :icon="CalendarClock"
            :title="t('ai.futureTaskTab')"
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
                </div>
              </div>
              <Button
                :disabled="!canCancelFutureTask(item.status) || cancellingTaskId === item.task_id"
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
      </TabsContent>
    </Tabs>
  </PageScaffold>
</template>
