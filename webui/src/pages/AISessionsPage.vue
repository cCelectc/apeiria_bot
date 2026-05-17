<script setup lang="ts">
import type {
  AIManagedSessionDetailItem,
  AIManagedSessionItem,
  AIManagedSessionMessageItem,
  AIManagedSessionTraceItem,
} from '@/api/ai'
import type { WorkbenchMetricItem, WorkbenchTone } from '@/components/management'
import {
  BotOff,
  Bug,
  MessageSquare,
  RefreshCw,
  RotateCcw,
  Route,
  Search,
  ShieldCheck,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useAISessionsTab } from '@/composables/useAISessionsTab'

const { t } = useI18n()
defineProps<{
  embedded?: boolean
}>()
const router = useRouter()
const errorMessage = ref('')
const resetDialogVisible = ref(false)
const sessionLimitOptions = [20, 50, 100]
const messageLimitOptions = [20, 50, 100, 200]

const {
  ALL_FILTER,
  UNASSIGNED_PERSONA,
  disabledCount,
  enabledCount,
  filteredSessions,
  filters,
  loadSessionDetail,
  loadSessions,
  loadingDetail,
  loadingSessions,
  personaSelection,
  personas,
  refreshSelectedDetail,
  resetContext,
  resettingContext,
  savingEnabled,
  savingPersona,
  selectedDetail,
  selectedSession,
  selectedSessionId,
  sessions,
  setAIEnabled,
  setSessionPersona,
} = useAISessionsTab(t)

const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: MessageSquare,
    key: 'sessions',
    label: t('ai.sessionsTab'),
    value: sessions.value.length,
  },
  {
    icon: ShieldCheck,
    key: 'enabled',
    label: t('ai.sessionEnabled'),
    tone: 'success',
    value: enabledCount.value,
  },
  {
    icon: BotOff,
    key: 'disabled',
    label: t('ai.sessionDisabled'),
    tone: disabledCount.value > 0 ? 'warning' : 'default',
    value: disabledCount.value,
  },
  {
    key: 'messages',
    label: t('ai.sessionMessageCount'),
    tone: 'info',
    value: sessions.value.reduce((total, item) => total + item.message_count, 0),
  },
])
const selectedSummary = computed(() => {
  const detail = selectedDetail.value
  const session = selectedSession.value
  if (!detail && !session) {
    return t('ai.noManagedSessionHint')
  }
  return detail
    ? sourceSummary(detail)
    : sourceSummary(session as AIManagedSessionItem)
})
const detailSummaryItems = computed(() => (
  selectedDetail.value ? buildSummaryItems(selectedDetail.value) : []
))
const sortedMessages = computed(() => (
  [...(selectedDetail.value?.recent_messages ?? [])].sort(
    (left, right) => left.created_at.localeCompare(right.created_at),
  )
))
const sortedTraces = computed(() => (
  [...(selectedDetail.value?.trace_entries ?? [])].sort(
    (left, right) => right.created_at.localeCompare(left.created_at),
  )
))

async function loadData() {
  errorMessage.value = ''
  try {
    await loadSessions()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.sessionLoadFailed'))
  }
}

async function confirmResetContext() {
  await resetContext()
  resetDialogVisible.value = false
}

function handleAIEnabledUpdate(value: unknown) {
  void setAIEnabled(value === true)
}

function handlePersonaUpdate(value: unknown) {
  void setSessionPersona(typeof value === 'string' ? value : UNASSIGNED_PERSONA)
}

async function openPromptPreview() {
  await router.push({
    name: 'ai',
    query: {
      area: 'debug',
      debug: 'conversations',
      session: selectedDetail.value?.prompt_preview_session_id || selectedSessionId.value,
    },
  })
}

async function openTrace(trace?: AIManagedSessionTraceItem) {
  await router.push({
    name: 'ai',
    query: {
      area: 'debug',
      debug: 'conversations',
      trace: trace?.trace_id,
      session: selectedSessionId.value,
    },
  })
}

function sessionTitle(item: AIManagedSessionItem | AIManagedSessionDetailItem) {
  return item.source_labels.title
    || item.source_labels.chat
    || item.source_labels.group
    || item.source_labels.user
    || item.subject_id
}

function sourceSummary(item: AIManagedSessionItem | AIManagedSessionDetailItem) {
  return `${item.platform_id} / ${item.platform_type} / ${item.message_type}`
}

function formatTime(value: string | null | undefined) {
  if (!value) {
    return t('common.none')
  }
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
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
  if (['skipped', 'disabled'].includes(value)) {
    return 'warning'
  }
  return 'default'
}

function messageText(item: AIManagedSessionMessageItem) {
  return item.text_content.trim() || t('common.noData')
}

function tokenLabel(value: number | null | undefined) {
  return value == null ? t('common.none') : value.toLocaleString()
}

function buildSummaryItems(detail: AIManagedSessionDetailItem) {
  return [
    {
      key: 'usage',
      rows: summaryRows({
        call_count: detail.usage.call_count,
        input_tokens: detail.usage.input_tokens,
        missing_usage_count: detail.usage.missing_usage_count,
        output_tokens: detail.usage.output_tokens,
        total_tokens: detail.usage.total_tokens,
      }),
      title: t('ai.sessionUsageSummary'),
    },
    {
      key: 'model',
      rows: summaryRows(detail.model_summary),
      title: t('ai.sessionModelSummary'),
    },
    {
      key: 'strategy',
      rows: summaryRows(detail.strategy_summary),
      title: t('ai.sessionStrategySummary'),
    },
    {
      key: 'tools',
      rows: summaryRows(detail.tool_summary),
      title: t('ai.sessionToolSummary'),
    },
    {
      key: 'diagnostics',
      rows: summaryRows(detail.diagnostics),
      title: t('ai.sessionDiagnostics'),
    },
  ]
}

function summaryRows(record: Record<string, string | number | null>) {
  return Object.entries(record).map(([key, value]) => ({
    key,
    value: value == null || value === '' ? t('common.none') : String(value),
  }))
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :embedded="embedded"
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.sessions')"
    :title="t('ai.sessionsTab')"
  >
    <template #actions>
      <Button :disabled="loadingSessions" variant="secondary" @click="loadData">
        <RefreshCw :class="{ 'animate-spin': loadingSessions }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" compact />

    <SplitPane wide-sidebar>
      <template #sidebar>
        <Panel :title="t('ai.managedSessions')">
          <template #actions>
            <Select v-model="filters.limit" @update:model-value="loadSessions">
              <SelectTrigger class="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem v-for="option in sessionLimitOptions" :key="option" :value="option">
                    {{ option }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </template>

          <div class="ai-session-filter">
            <div class="ai-session-filter__search">
              <Search :size="15" />
              <Input v-model="filters.query" :placeholder="t('common.search')" />
            </div>
            <Select v-model="filters.enabled">
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem :value="ALL_FILTER">{{ t('common.all') }}</SelectItem>
                  <SelectItem value="enabled">{{ t('ai.sessionEnabled') }}</SelectItem>
                  <SelectItem value="disabled">{{ t('ai.sessionDisabled') }}</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>

          <LoadingSkeleton v-if="loadingSessions && sessions.length === 0" :rows="5" />
          <EmptyState
            v-else-if="filteredSessions.length === 0"
            :icon="MessageSquare"
            :text="t('ai.noManagedSessionHint')"
            :title="t('ai.noManagedSessions')"
          />
          <SelectableList v-else>
            <SelectableListItem
              v-for="item in filteredSessions"
              :key="item.session_id"
              :active="selectedSessionId === item.session_id"
              @click="loadSessionDetail(item.session_id)"
            >
              <div class="ai-data-list-item">
                <div class="ai-data-list-item__main">
                  <strong>{{ sessionTitle(item) }}</strong>
                  <span>{{ sourceSummary(item) }} / {{ formatTime(item.last_message_at || item.last_observed_at) }}</span>
                </div>
                <StatusBadge
                  :label="item.ai_enabled ? t('ai.sessionEnabled') : t('ai.sessionDisabled')"
                  :tone="item.ai_enabled ? 'success' : 'warning'"
                />
              </div>
            </SelectableListItem>
          </SelectableList>
        </Panel>
      </template>

      <div class="ai-data-stack">
        <Panel :subtitle="selectedSummary" :title="t('ai.sessionDetail')">
          <template #actions>
            <Select v-model="filters.messageLimit">
              <SelectTrigger class="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem v-for="option in messageLimitOptions" :key="option" :value="option">
                    {{ option }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <Button
              :disabled="!selectedSessionId || loadingDetail"
              size="sm"
              variant="secondary"
              @click="refreshSelectedDetail"
            >
              <RefreshCw :class="{ 'animate-spin': loadingDetail }" :size="15" />
              {{ t('common.refresh') }}
            </Button>
          </template>

          <LoadingSkeleton v-if="loadingDetail && !selectedDetail" :rows="4" />
          <EmptyState
            v-else-if="!selectedDetail"
            :icon="MessageSquare"
            :text="t('ai.noManagedSessionHint')"
            :title="t('ai.noManagedSessionSelected')"
          />
          <div v-else class="ai-data-form">
            <div class="ai-data-form__meta">
              <Badge variant="secondary">{{ t('ai.sessionId') }}: {{ selectedDetail.session_id }}</Badge>
              <Badge variant="outline">{{ t('ai.sessionSubject') }}: {{ selectedDetail.subject_id }}</Badge>
              <Badge variant="outline">{{ t('ai.sessionResetBoundary') }}: {{ formatTime(selectedDetail.reset_boundary_at) }}</Badge>
              <Badge variant="outline">{{ t('ai.usageTotalTokens') }}: {{ tokenLabel(selectedDetail.usage.total_tokens) }}</Badge>
              <Badge variant="outline">{{ t('ai.usageMissing') }}: {{ selectedDetail.usage.missing_usage_count }}</Badge>
            </div>

            <div class="ai-data-grid-2">
              <div class="ai-data-switch-row">
                <div>
                  <strong>{{ t('ai.sessionAIEnabled') }}</strong>
                  <span>{{ selectedDetail.ai_enabled ? t('ai.sessionEnabled') : t('ai.sessionDisabled') }}</span>
                </div>
                <Switch
                  :disabled="savingEnabled"
                  :model-value="selectedDetail.ai_enabled"
                  @update:model-value="handleAIEnabledUpdate"
                />
              </div>

              <FormField :label="t('ai.sessionPersona')">
                <Select
                  :disabled="savingPersona"
                  :model-value="personaSelection"
                  @update:model-value="handlePersonaUpdate"
                >
                  <SelectTrigger>
                    <SelectValue :placeholder="t('common.none')" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem :value="UNASSIGNED_PERSONA">{{ t('common.none') }}</SelectItem>
                      <SelectItem
                        v-for="item in personas"
                        :key="item.persona_id"
                        :value="item.persona_id"
                      >
                        {{ item.name }}
                      </SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </FormField>
            </div>

            <div class="ai-data-actions">
              <Button variant="secondary" @click="openPromptPreview">
                <Route :size="16" />
                {{ t('ai.sessionPromptPreview') }}
              </Button>
              <Button variant="secondary" @click="openTrace()">
                <Bug :size="16" />
                {{ t('ai.sessionTraceEntry') }}
              </Button>
              <Button
                :disabled="resettingContext"
                variant="destructive"
                @click="resetDialogVisible = true"
              >
                <RotateCcw :class="{ 'animate-spin': resettingContext }" :size="16" />
                {{ t('ai.sessionContextReset') }}
              </Button>
            </div>
          </div>
        </Panel>

        <Panel :title="t('ai.sessionReadOnlySummaries')">
          <EmptyState
            v-if="!selectedDetail"
            :icon="Route"
            :title="t('common.noData')"
          />
          <div v-else class="ai-session-summary-grid">
            <article
              v-for="summary in detailSummaryItems"
              :key="summary.key"
              class="ai-session-summary"
            >
              <strong>{{ summary.title }}</strong>
              <dl v-if="summary.rows.length > 0">
                <template v-for="row in summary.rows" :key="row.key">
                  <dt>{{ row.key }}</dt>
                  <dd>{{ row.value }}</dd>
                </template>
              </dl>
              <span v-else>{{ t('common.none') }}</span>
            </article>
          </div>
        </Panel>

        <Panel :title="t('ai.sessionRecentMessages')">
          <LoadingSkeleton v-if="loadingDetail" :rows="4" />
          <EmptyState
            v-else-if="sortedMessages.length === 0"
            :icon="MessageSquare"
            :title="t('common.noData')"
          />
          <div v-else class="ai-session-message-list">
            <article
              v-for="message in sortedMessages"
              :key="message.message_id"
              class="ai-session-message"
              :class="{ 'ai-session-message--before-reset': message.before_reset_boundary }"
            >
              <div class="ai-debug-turn__meta">
                <Badge variant="secondary">{{ message.author_role }}</Badge>
                <Badge variant="outline">{{ formatTime(message.created_at) }}</Badge>
                <Badge v-if="message.model_name" variant="outline">{{ message.model_name }}</Badge>
                <StatusBadge
                  v-if="message.before_reset_boundary"
                  :label="t('ai.sessionBeforeReset')"
                  tone="warning"
                />
              </div>
              <p>{{ messageText(message) }}</p>
            </article>
          </div>
        </Panel>

        <Panel :title="t('ai.sessionTraceEntry')">
          <EmptyState
            v-if="sortedTraces.length === 0"
            :icon="Bug"
            :title="t('common.noData')"
          />
          <div v-else class="ai-session-trace-list">
            <article
              v-for="trace in sortedTraces"
              :key="trace.trace_id"
              class="ai-session-trace"
            >
              <div>
                <strong>{{ trace.trace_id }}</strong>
                <span>{{ formatTime(trace.created_at) }}</span>
              </div>
              <StatusBadge :label="trace.terminal_status" :tone="statusTone(trace.terminal_status)" />
              <p>{{ trace.skip_reason || t('common.none') }}</p>
              <Button size="sm" variant="secondary" @click="openTrace(trace)">
                <Bug :size="15" />
                {{ t('ai.sessionTraceEntry') }}
              </Button>
            </article>
          </div>
        </Panel>
      </div>
    </SplitPane>

    <Dialog v-model:open="resetDialogVisible">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ t('ai.sessionResetConfirmTitle') }}</DialogTitle>
          <DialogDescription>
            {{ t('ai.sessionResetConfirm') }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" @click="resetDialogVisible = false">
            {{ t('common.cancel') }}
          </Button>
          <Button :disabled="resettingContext" variant="destructive" @click="confirmResetContext">
            <RotateCcw :class="{ 'animate-spin': resettingContext }" :size="16" />
            {{ t('common.confirm') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </PageScaffold>
</template>
