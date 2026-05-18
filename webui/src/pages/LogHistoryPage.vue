<script setup lang="ts">
import type { LogHistoryQuery } from '@/api/logs'
import type { WorkbenchMetricItem } from '@/components/management'
import axios from 'axios'
import {
  AlertTriangle,
  Database,
  Download,
  Eye,
  History,
  Search,
} from 'lucide-vue-next'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { getErrorMessage } from '@/api/client'
import { getLogHistory, getLogSources } from '@/api/logs'
import {
  EmptyState,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
  StatusBadge,
} from '@/components/management'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import {
  exportJsonl,
  formatDateTimeLocal,
  type LogEntry,
  logLevelTone,
  toLogEntry,
} from '@/composables/useLogUtils'

interface FiltersState {
  end: string
  level: string
  search: string
  source: string
  start: string
}

const ALL_LEVELS = '__all__'
const ALL_SOURCES = '__all__'
const PAGE_SIZE = 30
const levelOptions = ['DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL']
const timePresets = [
  { key: '15m', hours: 0.25, labelKey: 'logs.last15Minutes' },
  { key: '1h', hours: 1, labelKey: 'logs.lastHour' },
  { key: '24h', hours: 24, labelKey: 'logs.last24Hours' },
  { key: '7d', hours: 24 * 7, labelKey: 'logs.last7Days' },
]

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const draftFilters = reactive<FiltersState>({
  end: '',
  level: ALL_LEVELS,
  search: '',
  source: ALL_SOURCES,
  start: '',
})
const appliedFilters = ref<FiltersState>(cloneFilters(draftFilters))
const entries = ref<LogEntry[]>([])
const sourceOptions = ref<string[]>([])
const showAccessLogs = ref(false)
const appliedShowAccessLogs = ref(false)
const loading = ref(false)
const beforeOffset = ref(0)
const total = ref(0)
const errorMessage = ref('')
const selectedEntryId = ref('')
const listContainer = ref<HTMLElement | null>(null)
let activeHistoryRequest: AbortController | null = null
let autoQueryTimer: ReturnType<typeof setTimeout> | null = null

const highSignalCount = computed(() =>
  entries.value.filter(entry => ['ERROR', 'CRITICAL', 'WARNING'].includes(entry.level)).length,
)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const currentPage = computed(() => Math.floor(beforeOffset.value / PAGE_SIZE) + 1)
const canGoPrev = computed(() => currentPage.value > 1)
const canGoNext = computed(() => currentPage.value < totalPages.value)
const validationMessage = computed(() => {
  if (draftFilters.start && draftFilters.end && draftFilters.start > draftFilters.end) {
    return t('logs.invalidTimeRange')
  }
  return ''
})
const hasAnyFilter = computed(() =>
  Boolean(
    draftFilters.search
    || draftFilters.source
    || draftFilters.start
    || draftFilters.end
    || draftFilters.level !== ALL_LEVELS
    || showAccessLogs.value,
  ),
)
const hasPendingChanges = computed(() =>
  JSON.stringify(draftFilters) !== JSON.stringify(appliedFilters.value)
  || showAccessLogs.value !== appliedShowAccessLogs.value,
)
const visibleSourceOptions = computed(() =>
  sourceOptions.value.filter(item => showAccessLogs.value || item !== 'uvicorn.access'),
)
const historyMetrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: Database,
    key: 'total',
    label: t('logs.totalRecords'),
    value: total.value,
  },
  {
    icon: Eye,
    key: 'visible',
    label: t('logs.visibleCount'),
    tone: 'info',
    value: entries.value.length,
  },
  {
    icon: AlertTriangle,
    key: 'signal',
    label: t('logs.errorCount'),
    tone: highSignalCount.value > 0 ? 'warning' : 'success',
    value: highSignalCount.value,
  },
  {
    icon: History,
    key: 'page',
    label: t('logs.currentPage'),
    value: `${currentPage.value} / ${totalPages.value}`,
  },
])
const activeFilterChips = computed(() => {
  const chips: Array<{ key: string, label: string }> = []
  if (appliedFilters.value.search) {
    chips.push({ key: 'search', label: `${t('logs.search')}: ${appliedFilters.value.search}` })
  }
  if (appliedFilters.value.level !== ALL_LEVELS) {
    chips.push({ key: 'level', label: `${t('logs.level')}: ${appliedFilters.value.level}` })
  }
  if (appliedFilters.value.source && appliedFilters.value.source !== ALL_SOURCES) {
    chips.push({ key: 'source', label: `${t('logs.source')}: ${appliedFilters.value.source}` })
  }
  if (appliedFilters.value.start) {
    chips.push({ key: 'start', label: `${t('logs.startTime')}: ${formatDateTimeLabel(appliedFilters.value.start)}` })
  }
  if (appliedFilters.value.end) {
    chips.push({ key: 'end', label: `${t('logs.endTime')}: ${formatDateTimeLabel(appliedFilters.value.end)}` })
  }
  return chips
})
const resultsLabel = computed(() => {
  if (loading.value && entries.value.length === 0) {
    return t('common.loading')
  }
  if (entries.value.length === 0) {
    return t('logs.noHistory')
  }
  return t('logs.resultsLoaded', { count: entries.value.length })
})

function cloneFilters(filters: FiltersState): FiltersState {
  return {
    end: filters.end,
    level: filters.level,
    search: filters.search,
    source: filters.source,
    start: filters.start,
  }
}

function readFiltersFromRoute(): FiltersState {
  const query = route.query
  return {
    end: typeof query.end === 'string' ? query.end : '',
    level: typeof query.level === 'string' ? query.level : ALL_LEVELS,
    search: typeof query.search === 'string' ? query.search : '',
    source: typeof query.source === 'string' ? query.source : ALL_SOURCES,
    start: typeof query.start === 'string' ? query.start : '',
  }
}

async function syncRouteQuery(filters: FiltersState) {
  const nextQuery: Record<string, string> = {}
  if (filters.search) nextQuery.search = filters.search
  if (filters.level && filters.level !== ALL_LEVELS) nextQuery.level = filters.level
  if (filters.source && filters.source !== ALL_SOURCES) nextQuery.source = filters.source
  if (filters.start) nextQuery.start = filters.start
  if (filters.end) nextQuery.end = filters.end
  await router.replace({ query: nextQuery })
}

function buildQuery(before = 0): LogHistoryQuery {
  return {
    before,
    end: appliedFilters.value.end || undefined,
    include_access: appliedShowAccessLogs.value,
    level: appliedFilters.value.level !== ALL_LEVELS
      ? appliedFilters.value.level
      : undefined,
    limit: PAGE_SIZE,
    search: appliedFilters.value.search || undefined,
    source: appliedFilters.value.source && appliedFilters.value.source !== ALL_SOURCES
      ? appliedFilters.value.source
      : undefined,
    start: appliedFilters.value.start || undefined,
  }
}

async function fetchHistory(before = 0) {
  activeHistoryRequest?.abort()
  activeHistoryRequest = new AbortController()
  const currentRequest = activeHistoryRequest
  loading.value = true
  errorMessage.value = ''

  try {
    const response = await getLogHistory(buildQuery(before), currentRequest.signal)
    entries.value = response.data.items.map(item => toLogEntry(item))
    total.value = response.data.total
    beforeOffset.value = before
    selectedEntryId.value = ''
    await nextTick()
    listContainer.value?.scrollTo({ top: 0 })
  } catch (error) {
    if (axios.isCancel(error)) {
      return
    }
    errorMessage.value = getErrorMessage(error, t('logs.historyQueryFailed'))
  } finally {
    if (activeHistoryRequest === currentRequest) {
      activeHistoryRequest = null
    }
    loading.value = false
  }
}

async function runQuery() {
  clearAutoQueryTimer()
  if (validationMessage.value) {
    return
  }
  if (!showAccessLogs.value && draftFilters.source === 'uvicorn.access') {
    draftFilters.source = ALL_SOURCES
  }
  appliedFilters.value = cloneFilters(draftFilters)
  appliedShowAccessLogs.value = showAccessLogs.value
  await syncRouteQuery(appliedFilters.value)
  await fetchHistory(0)
}

async function resetFilters() {
  clearAutoQueryTimer()
  draftFilters.search = ''
  draftFilters.level = ALL_LEVELS
  draftFilters.source = ALL_SOURCES
  draftFilters.start = ''
  draftFilters.end = ''
  showAccessLogs.value = false
  appliedFilters.value = cloneFilters(draftFilters)
  appliedShowAccessLogs.value = showAccessLogs.value
  await syncRouteQuery(appliedFilters.value)
  await fetchHistory(0)
}

function goToPage(page: number) {
  const nextPage = Math.min(Math.max(page, 1), totalPages.value)
  if (nextPage !== currentPage.value) {
    void fetchHistory((nextPage - 1) * PAGE_SIZE)
  }
}

function selectEntry(id: string) {
  selectedEntryId.value = selectedEntryId.value === id ? '' : id
}

function applyTimePreset(hours: number) {
  const end = new Date()
  const start = new Date(end.getTime() - hours * 60 * 60 * 1000)
  draftFilters.start = formatDateTimeLocal(start)
  draftFilters.end = formatDateTimeLocal(end)
}

function clearTimeRange() {
  draftFilters.start = ''
  draftFilters.end = ''
}

function formatDateTimeLabel(value: string) {
  return value.replace('T', ' ')
}

function clearAutoQueryTimer() {
  if (autoQueryTimer !== null) {
    clearTimeout(autoQueryTimer)
    autoQueryTimer = null
  }
}

function scheduleAutoQuery() {
  clearAutoQueryTimer()
  if (validationMessage.value || !hasPendingChanges.value) {
    return
  }
  autoQueryTimer = window.setTimeout(() => {
    autoQueryTimer = null
    void runQuery()
  }, 3000)
}

function exportLogs() {
  exportJsonl(entries.value, `apeiria-history-logs-${Date.now()}.jsonl`)
}

watch(() => route.query, query => {
  clearAutoQueryTimer()
  const nextFilters = {
    end: typeof query.end === 'string' ? query.end : '',
    level: typeof query.level === 'string' ? query.level : ALL_LEVELS,
    search: typeof query.search === 'string' ? query.search : '',
    source: typeof query.source === 'string' ? query.source : ALL_SOURCES,
    start: typeof query.start === 'string' ? query.start : '',
  }

  if (JSON.stringify(nextFilters) === JSON.stringify(appliedFilters.value)) {
    return
  }

  Object.assign(draftFilters, nextFilters)
  appliedFilters.value = cloneFilters(nextFilters)
  void fetchHistory(0)
})

watch(
  () => [
    draftFilters.search,
    draftFilters.level,
    draftFilters.source,
    draftFilters.start,
    draftFilters.end,
  ],
  scheduleAutoQuery,
)

watch(showAccessLogs, enabled => {
  clearAutoQueryTimer()
  if (!enabled && draftFilters.source === 'uvicorn.access') {
    draftFilters.source = ALL_SOURCES
  }
  scheduleAutoQuery()
})

onMounted(() => {
  const initialFilters = readFiltersFromRoute()
  Object.assign(draftFilters, initialFilters)
  appliedFilters.value = cloneFilters(initialFilters)
  appliedShowAccessLogs.value = showAccessLogs.value
  void getLogSources().then(response => {
    sourceOptions.value = response.data.items
  }).catch(() => {
    sourceOptions.value = []
  })
  void fetchHistory(0)
})

onBeforeUnmount(() => {
  clearAutoQueryTimer()
  activeHistoryRequest?.abort()
})
</script>

<template>
  <PageScaffold
    dense
    :error-message="errorMessage"
    full-height
    :subtitle="t('logs.historyDescription')"
    :title="t('logs.historyTitle')"
  >
    <template #actions>
      <Button :disabled="entries.length === 0" variant="ghost" @click="exportLogs">
        <Download :size="16" />
        {{ t('logs.export') }}
      </Button>
    </template>

    <MetricStrip :items="historyMetrics" compact />

    <Panel :title="t('logs.queryHistory')">
      <div class="logs-history-filter">
        <div class="logs-search">
          <Search :size="16" />
          <Input
            v-model.trim="draftFilters.search"
            :aria-label="t('logs.search')"
            :placeholder="t('logs.search')"
            @keydown.enter.prevent="runQuery"
          />
        </div>

        <div class="logs-field">
          <Label>{{ t('logs.level') }}</Label>
          <Select v-model="draftFilters.level">
            <SelectTrigger class="logs-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="ALL_LEVELS">
                {{ t('common.all') }}
              </SelectItem>
              <SelectItem
                v-for="level in levelOptions"
                :key="level"
                :value="level"
              >
                {{ level }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="logs-field">
          <Label>{{ t('logs.source') }}</Label>
          <Select v-model="draftFilters.source">
            <SelectTrigger class="logs-select">
              <SelectValue :placeholder="t('logs.sourceHint')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="ALL_SOURCES">
                {{ t('common.all') }}
              </SelectItem>
              <SelectItem
                v-for="source in visibleSourceOptions"
                :key="source"
                :value="source"
              >
                {{ source }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <label class="logs-switch">
          <Switch v-model="showAccessLogs" />
          <span>{{ t('logs.showAccessLogs') }}</span>
        </label>
      </div>

      <div class="logs-history-filter logs-history-filter--time">
        <div class="logs-field">
          <Label>{{ t('logs.startTime') }}</Label>
          <Input v-model="draftFilters.start" type="datetime-local" />
        </div>
        <div class="logs-field">
          <Label>{{ t('logs.endTime') }}</Label>
          <Input v-model="draftFilters.end" type="datetime-local" />
        </div>
        <div class="logs-presets">
          <Button
            v-for="preset in timePresets"
            :key="preset.key"
            size="sm"
            variant="secondary"
            @click="applyTimePreset(preset.hours)"
          >
            {{ t(preset.labelKey) }}
          </Button>
          <Button
            v-if="draftFilters.start || draftFilters.end"
            size="sm"
            variant="ghost"
            @click="clearTimeRange"
          >
            {{ t('logs.clearTimeRange') }}
          </Button>
        </div>
      </div>

      <Alert v-if="validationMessage" variant="default">
        <AlertDescription>{{ validationMessage }}</AlertDescription>
      </Alert>

      <div class="logs-query-actions">
        <div class="logs-active-filters">
          <Badge
            v-for="chip in activeFilterChips"
            :key="chip.key"
            variant="secondary"
          >
            {{ chip.label }}
          </Badge>
        </div>
        <div>
          <Button
            :disabled="!hasAnyFilter || loading"
            variant="ghost"
            @click="resetFilters"
          >
            {{ t('logs.resetFilters') }}
          </Button>
          <Button
            :disabled="Boolean(validationMessage) || loading"
            @click="runQuery"
          >
            <Search :size="16" />
            {{ t('logs.query') }}
          </Button>
        </div>
      </div>
    </Panel>

    <Panel class="logs-history-panel">
      <div class="logs-history-result-bar">
        <span>{{ resultsLabel }}</span>
        <Badge v-if="hasPendingChanges" variant="outline">
          {{ t('logs.queryStatePartial') }}
        </Badge>
      </div>

      <LoadingSkeleton v-if="loading && entries.length === 0" :rows="8" />
      <EmptyState
        v-else-if="entries.length === 0"
        :icon="History"
        :title="t('logs.noHistory')"
      />
      <div v-else ref="listContainer" class="logs-history-list">
        <article
          v-for="entry in entries"
          :key="entry.id"
          class="logs-history-item"
          :class="{ 'logs-history-item--active': selectedEntryId === entry.id }"
        >
          <button
            class="logs-history-row"
            type="button"
            @click="selectEntry(entry.id)"
          >
            <StatusBadge :label="entry.level" :tone="logLevelTone(entry.level)" />
            <span class="logs-history-row__source">{{ entry.source }}</span>
            <span class="logs-history-row__time">{{ entry.timestamp }}</span>
            <span class="logs-history-row__message">{{ entry.message }}</span>
          </button>

          <div v-if="selectedEntryId === entry.id" class="logs-history-detail">
            <div class="logs-history-detail__meta">
              <StatusBadge :label="entry.level" :tone="logLevelTone(entry.level)" />
              <span>{{ entry.source }}</span>
              <span>{{ entry.timestamp }}</span>
            </div>
            <div class="logs-history-detail__message">{{ entry.message }}</div>
            <pre>{{ entry.raw }}</pre>
            <pre v-if="Object.keys(entry.extra).length > 0">{{ JSON.stringify(entry.extra, null, 2) }}</pre>
          </div>
        </article>
      </div>

      <div class="logs-pagination">
        <span>
          {{ t('logs.paginationStatus', { page: currentPage, totalPages, total }) }}
        </span>
        <div>
          <Button :disabled="loading || !canGoPrev" variant="ghost" @click="goToPage(1)">
            {{ t('logs.firstPage') }}
          </Button>
          <Button :disabled="loading || !canGoPrev" variant="ghost" @click="goToPage(currentPage - 1)">
            {{ t('logs.prevPage') }}
          </Button>
          <Button :disabled="loading || !canGoNext" variant="secondary" @click="goToPage(currentPage + 1)">
            {{ t('logs.nextPage') }}
          </Button>
          <Button :disabled="loading || !canGoNext" variant="ghost" @click="goToPage(totalPages)">
            {{ t('logs.lastPage') }}
          </Button>
        </div>
      </div>
    </Panel>
  </PageScaffold>
</template>
