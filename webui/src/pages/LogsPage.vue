<script setup lang="ts">
import {
  ChevronDown,
  Download,
  Plug,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Trash2,
  Unplug,
} from 'lucide-vue-next'
import { computed, nextTick, onActivated, onDeactivated, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { getErrorMessage } from '@/api/client'
import { getLogHistory, type LogItem } from '@/api/logs'
import {
  EmptyState,
  LoadingSkeleton,
  PageScaffold,
  Panel,
  StatusBadge,
} from '@/components/management'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  exportJsonl,
  type LogEntry,
  logEntryKey,
  logLevelTone,
  logMatchesFilters,
  normalizeLogFrame,
  toLogEntry,
} from '@/composables/useLogUtils'
import {
  buildLiveLogRouteQuery,
  liveLogRouteStateEquals,
  normalizeLiveLogRouteState,
  type LiveLogRouteState,
} from '@/utils/liveLogRouteState'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const logs = ref<LogEntry[]>([])
const connected = ref(false)
const autoScroll = ref(true)
const search = ref('')
const selectedLevels = ref<string[]>([])
const selectedSources = ref<string[]>([])
const showAccessLogs = ref(false)
const showRawRecords = ref(false)
const advancedFiltersOpen = ref(false)
const loadingHistory = ref(false)
const bootstrapError = ref('')
const recentHistoryCount = ref(0)
const logContainer = ref<HTMLElement | null>(null)
const pendingLiveLogs: LogEntry[] = []
const MAX_LIVE_LOGS = 500
let ws: WebSocket | null = null
let primingHistory = false
let recentHistoryRequestSeq = 0
let syncingRouteState = false

const levelOptions = computed(() =>
  Array.from(new Set(logs.value.map(item => item.level))).sort(),
)
const sourceOptions = computed(() =>
  Array.from(new Set(
    logs.value
      .filter(item => showAccessLogs.value || item.source !== 'uvicorn.access')
      .map(item => item.source),
  )).sort(),
)
const filteredLogs = computed(() =>
  logs.value.filter(entry =>
    logMatchesFilters(entry, {
      levels: selectedLevels.value,
      search: search.value,
      showAccessLogs: showAccessLogs.value,
      sources: selectedSources.value,
    }),
  ),
)
const highSignalCount = computed(() =>
  filteredLogs.value.filter(item => ['WARNING', 'ERROR', 'CRITICAL'].includes(item.level)).length,
)
const statusSummary = computed(() => [
  { key: 'total', label: t('logs.totalCount'), value: logs.value.length },
  { key: 'visible', label: t('logs.visibleCount'), value: filteredLogs.value.length },
  { key: 'signal', label: t('logs.errorCount'), value: highSignalCount.value },
  { key: 'recent', label: t('logs.recentCount'), value: recentHistoryCount.value },
])
const liveAdvancedFilterCount = computed(() =>
  selectedLevels.value.length
  + selectedSources.value.length
  + (showAccessLogs.value ? 1 : 0),
)
const hasLiveFilters = computed(() =>
  Boolean(
    search.value
    || selectedLevels.value.length
    || selectedSources.value.length
    || showAccessLogs.value,
  ),
)
const liveFilterChips = computed(() => {
  const chips: Array<{ key: string, label: string }> = []
  if (search.value) {
    chips.push({ key: 'search', label: `${t('logs.search')}: ${search.value}` })
  }
  if (selectedLevels.value.length) {
    chips.push({
      key: 'levels',
      label: `${t('logs.level')}: ${selectedLevels.value.join(', ')}`,
    })
  }
  if (selectedSources.value.length) {
    chips.push({
      key: 'sources',
      label: `${t('logs.source')}: ${selectedSources.value.join(', ')}`,
    })
  }
  if (showAccessLogs.value) {
    chips.push({ key: 'access', label: t('logs.showAccessLogs') })
  }
  return chips
})

function connect() {
  disconnect()
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${proto}//${location.host}/api/logs/ws`)

  ws.addEventListener('open', () => {
    const token = localStorage.getItem('token')
    if (token) {
      ws?.send(token)
    }
    connected.value = true
  })

  ws.addEventListener('message', event => {
    const entry = normalizeLogFrame(String(event.data))
    if (primingHistory) {
      pendingLiveLogs.push(entry)
      return
    }
    appendLiveLog(entry)
    scrollToBottomIfNeeded()
  })

  ws.addEventListener('close', () => {
    connected.value = false
  })
}

function disconnect() {
  ws?.close()
  ws = null
  connected.value = false
}

function clearLogs() {
  logs.value = []
  recentHistoryCount.value = 0
}

function resetLogsView() {
  disconnect()
  logs.value = []
  bootstrapError.value = ''
  recentHistoryCount.value = 0
  pendingLiveLogs.length = 0
  primingHistory = false
}

async function loadRecentHistory(options: { preserveLiveLogs?: boolean } = {}) {
  const requestSeq = ++recentHistoryRequestSeq
  const preservedLiveLogs = options.preserveLiveLogs
    ? logs.value.slice(recentHistoryCount.value)
    : []
  loadingHistory.value = true
  bootstrapError.value = ''
  try {
    const response = await getLogHistory({
      before: 0,
      include_access: showAccessLogs.value,
      limit: 50,
    })
    if (requestSeq !== recentHistoryRequestSeq) {
      return
    }
    const historyLogs = response.data.items.slice().reverse().map((item: LogItem) => toLogEntry(item))
    const existingKeys = new Set(historyLogs.map(item => logEntryKey(item)))
    const mergedLogs = historyLogs.slice()
    for (const entry of preservedLiveLogs) {
      const entryKey = logEntryKey(entry)
      if (existingKeys.has(entryKey)) {
        continue
      }
      existingKeys.add(entryKey)
      mergedLogs.push(entry)
    }
    logs.value = mergedLogs
    recentHistoryCount.value = historyLogs.length
    await nextTick()
    logContainer.value?.scrollTo({ top: logContainer.value.scrollHeight })
  } catch (error) {
    if (requestSeq !== recentHistoryRequestSeq) {
      return
    }
    bootstrapError.value = getErrorMessage(error, t('logs.historyLoadFailed'))
  } finally {
    if (requestSeq === recentHistoryRequestSeq) {
      loadingHistory.value = false
    }
  }
}

async function initializeLogsView() {
  resetLogsView()
  primingHistory = true
  connect()
  try {
    await loadRecentHistory()
  } finally {
    flushPendingLiveLogs()
    primingHistory = false
  }
}

async function toggleConnection() {
  if (connected.value) {
    disconnect()
    return
  }
  if (logs.value.length === 0) {
    await initializeLogsView()
    return
  }
  connect()
}

function flushPendingLiveLogs() {
  const existingKeys = new Set(logs.value.map(item => logEntryKey(item)))
  for (const entry of pendingLiveLogs.splice(0)) {
    const entryKey = logEntryKey(entry)
    if (existingKeys.has(entryKey)) {
      continue
    }
    existingKeys.add(entryKey)
    appendLiveLog(entry)
  }
  scrollToBottomIfNeeded()
}

function appendLiveLog(entry: LogEntry) {
  logs.value.push(entry)
  const maxLogs = recentHistoryCount.value + MAX_LIVE_LOGS
  if (logs.value.length > maxLogs) {
    logs.value.splice(recentHistoryCount.value, logs.value.length - maxLogs)
  }
}

function scrollToBottomIfNeeded() {
  if (!autoScroll.value) {
    return
  }
  void nextTick(() => {
    logContainer.value?.scrollTo(0, logContainer.value.scrollHeight)
  })
}

function exportLogs() {
  exportJsonl(filteredLogs.value, `apeiria-live-logs-${Date.now()}.jsonl`)
}

function toggleLevel(level: string, checked: boolean | 'indeterminate') {
  selectedLevels.value = checked === true
    ? [...new Set([...selectedLevels.value, level])]
    : selectedLevels.value.filter(item => item !== level)
}

function toggleSource(source: string, checked: boolean | 'indeterminate') {
  selectedSources.value = checked === true
    ? [...new Set([...selectedSources.value, source])]
    : selectedSources.value.filter(item => item !== source)
}

function resetLiveFilters() {
  search.value = ''
  selectedLevels.value = []
  selectedSources.value = []
  showAccessLogs.value = false
}

function syncAdvancedFiltersOpen(event: Event) {
  advancedFiltersOpen.value = Boolean((event.currentTarget as HTMLDetailsElement | null)?.open)
}

function currentLiveLogRouteState(): LiveLogRouteState {
  return normalizeLiveLogRouteState(buildLiveLogRouteQuery({
    advanced: advancedFiltersOpen.value,
    levels: selectedLevels.value,
    search: search.value,
    showAccessLogs: showAccessLogs.value,
    showRawRecords: showRawRecords.value,
    sources: selectedSources.value,
  }))
}

async function syncLiveLogRouteQuery() {
  const nextQuery = buildLiveLogRouteQuery(currentLiveLogRouteState())
  const currentQuery = buildLiveLogRouteQuery(normalizeLiveLogRouteState(route.query))
  if (JSON.stringify(nextQuery) === JSON.stringify(currentQuery)) {
    return
  }
  await router.replace({ query: nextQuery })
}

function applyLiveLogRouteState(state: LiveLogRouteState) {
  syncingRouteState = true
  search.value = state.search
  selectedLevels.value = state.levels
  showAccessLogs.value = state.showAccessLogs
  showRawRecords.value = state.showRawRecords
  advancedFiltersOpen.value = state.advanced
  selectedSources.value = state.showAccessLogs
    ? state.sources
    : state.sources.filter(source => source !== 'uvicorn.access')
  void nextTick(() => {
    syncingRouteState = false
  })
}

watch(showAccessLogs, enabled => {
  if (!enabled) {
    selectedSources.value = selectedSources.value.filter(source => source !== 'uvicorn.access')
  }
  if (syncingRouteState) {
    return
  }
  if (!primingHistory && logs.value.length > 0) {
    void loadRecentHistory({ preserveLiveLogs: true })
  }
})

watch(
  [search, selectedLevels, selectedSources, showAccessLogs, showRawRecords, advancedFiltersOpen],
  () => {
    if (syncingRouteState) {
      return
    }
    void syncLiveLogRouteQuery()
  },
)

watch(() => route.query, query => {
  const nextState = normalizeLiveLogRouteState(query)
  const currentState = currentLiveLogRouteState()
  if (liveLogRouteStateEquals(nextState, currentState)) {
    return
  }
  const accessVisibilityChanged = nextState.showAccessLogs !== currentState.showAccessLogs
  applyLiveLogRouteState(nextState)
  if (accessVisibilityChanged && !primingHistory && logs.value.length > 0) {
    void loadRecentHistory({ preserveLiveLogs: true })
  }
})

onMounted(() => {
  applyLiveLogRouteState(normalizeLiveLogRouteState(route.query))
  void initializeLogsView()
})
onActivated(() => {
  if (!connected.value) {
    void initializeLogsView()
  }
})
onDeactivated(disconnect)
onUnmounted(disconnect)
</script>

<template>
  <PageScaffold class="logs-page" dense :title="t('logs.liveTitle')">
    <template #actions>
      <StatusBadge
        :label="connected ? t('logs.connected') : t('logs.disconnected')"
        :tone="connected ? 'success' : 'error'"
      />
      <Button variant="ghost" @click="toggleConnection">
        <component :is="connected ? Unplug : Plug" :size="16" />
        {{ connected ? t('logs.disconnect') : t('logs.connect') }}
      </Button>
      <Button
        :disabled="filteredLogs.length === 0"
        variant="ghost"
        @click="exportLogs"
      >
        <Download :size="16" />
        {{ t('logs.export') }}
      </Button>
      <Button :disabled="logs.length === 0" variant="ghost" @click="clearLogs">
        <Trash2 :size="16" />
        {{ t('logs.clear') }}
      </Button>
    </template>

    <Panel class="logs-toolbar-panel logs-live-filter-panel">
      <div class="logs-live-filter">
        <div class="logs-live-filter__primary">
          <div class="logs-search">
            <Search :size="16" />
            <Input
              v-model.trim="search"
              :aria-label="t('logs.search')"
              :placeholder="t('logs.search')"
            />
          </div>

          <div class="logs-view-switches">
            <label class="logs-switch">
              <Switch v-model="autoScroll" />
              <span>{{ t('logs.autoScroll') }}</span>
            </label>

            <label class="logs-switch">
              <Switch v-model="showRawRecords" />
              <span>{{ t('logs.showRawRecords') }}</span>
            </label>
          </div>
        </div>

        <details
          class="logs-advanced-filters"
          :open="advancedFiltersOpen"
          @toggle="syncAdvancedFiltersOpen"
        >
          <summary class="logs-advanced-filters__summary">
            <span class="logs-advanced-filters__title">
              <SlidersHorizontal :size="15" />
              {{ t('logs.advancedFilters') }}
            </span>
            <span class="logs-advanced-filters__meta">
              <Badge v-if="liveAdvancedFilterCount > 0" variant="secondary">
                {{ t('logs.activeFilterCount', { count: liveAdvancedFilterCount }) }}
              </Badge>
              <ChevronDown class="logs-advanced-filters__chevron" :size="16" />
            </span>
          </summary>

          <div class="logs-advanced-filters__content">
            <label class="logs-switch logs-access-filter">
              <Switch v-model="showAccessLogs" />
              <span>{{ t('logs.showAccessLogs') }}</span>
            </label>

            <div class="logs-chip-filter logs-chip-filter--inline">
              <div>
                <Label>{{ t('logs.level') }}</Label>
                <div class="logs-chip-list">
                  <label
                    v-for="level in levelOptions"
                    :key="level"
                    class="logs-check-chip"
                  >
                    <Checkbox
                      :checked="selectedLevels.includes(level)"
                      @update:checked="toggleLevel(level, $event)"
                    />
                    <span>{{ level }}</span>
                  </label>
                </div>
              </div>

              <div>
                <Label>{{ t('logs.source') }}</Label>
                <div class="logs-chip-list">
                  <label
                    v-for="source in sourceOptions"
                    :key="source"
                    class="logs-check-chip"
                  >
                    <Checkbox
                      :checked="selectedSources.includes(source)"
                      @update:checked="toggleSource(source, $event)"
                    />
                    <span>{{ source }}</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </details>

        <div class="logs-query-footer">
          <div class="logs-active-filters">
            <span v-if="liveFilterChips.length === 0" class="logs-active-filters__empty">
              {{ t('logs.noActiveFilters') }}
            </span>
            <Badge
              v-for="chip in liveFilterChips"
              :key="chip.key"
              variant="secondary"
            >
              {{ chip.label }}
            </Badge>
          </div>
          <div class="logs-query-footer__actions">
            <Button
              :disabled="!hasLiveFilters"
              variant="ghost"
              @click="resetLiveFilters"
            >
              <RefreshCw :size="16" />
              {{ t('logs.resetFilters') }}
            </Button>
          </div>
        </div>
      </div>
    </Panel>

    <Alert v-if="bootstrapError" variant="default">
      <AlertDescription>{{ bootstrapError }}</AlertDescription>
    </Alert>

    <Panel class="logs-stream-panel" title="logs://live">
      <template #actions>
        <div class="logs-status-strip logs-status-strip--panel">
          <StatusBadge
            v-for="item in statusSummary"
            :key="item.key"
            :label="`${item.label} ${item.value}`"
            :tone="item.key === 'signal' && highSignalCount > 0 ? 'warning' : 'default'"
          />
        </div>
      </template>

      <LoadingSkeleton v-if="loadingHistory && logs.length === 0" :rows="8" />
      <EmptyState
        v-else-if="filteredLogs.length === 0"
        :icon="RefreshCw"
        :title="t('logs.waiting')"
      />
      <div v-else ref="logContainer" class="logs-live-stream">
        <article
          v-for="entry in filteredLogs"
          :key="entry.id"
          :class="showRawRecords ? 'logs-live-row logs-live-row--raw' : 'logs-live-row'"
        >
          <template v-if="showRawRecords">
            <span class="logs-live-row__raw">{{ entry.raw }}</span>
          </template>
          <template v-else>
            <span class="logs-live-row__time">[{{ entry.timestamp.slice(11, 19) }}]</span>
            <StatusBadge :label="entry.level" :tone="logLevelTone(entry.level)" />
            <span class="logs-live-row__source">{{ entry.source }}</span>
            <span class="logs-live-row__message">{{ entry.message }}</span>
          </template>
        </article>
      </div>
    </Panel>
  </PageScaffold>
</template>
