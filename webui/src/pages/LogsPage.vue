<script setup lang="ts">
import type { WorkbenchMetricItem } from '@/components/management'
import { Download, Plug, RefreshCw, Search, Trash2, Unplug } from 'lucide-vue-next'
import { computed, nextTick, onActivated, onDeactivated, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import { getLogHistory, type LogItem } from '@/api/logs'
import {
  EmptyState,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
  StatusBadge,
} from '@/components/management'
import { Alert, AlertDescription } from '@/components/ui/alert'
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

const { t } = useI18n()
const logs = ref<LogEntry[]>([])
const connected = ref(false)
const autoScroll = ref(true)
const search = ref('')
const selectedLevels = ref<string[]>([])
const selectedSources = ref<string[]>([])
const showAccessLogs = ref(false)
const loadingHistory = ref(false)
const bootstrapError = ref('')
const recentHistoryCount = ref(0)
const logContainer = ref<HTMLElement | null>(null)
const pendingLiveLogs: LogEntry[] = []
const MAX_LIVE_LOGS = 500
let ws: WebSocket | null = null
let primingHistory = false

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
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    key: 'total',
    label: t('logs.totalCount'),
    value: logs.value.length,
  },
  {
    key: 'visible',
    label: t('logs.visibleCount'),
    tone: 'info',
    value: filteredLogs.value.length,
  },
  {
    key: 'signal',
    label: t('logs.errorCount'),
    tone: highSignalCount.value > 0 ? 'warning' : 'success',
    value: highSignalCount.value,
  },
  {
    key: 'recent',
    label: t('logs.recentCount'),
    value: recentHistoryCount.value,
  },
])

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
  selectedLevels.value = []
  selectedSources.value = []
  showAccessLogs.value = false
  search.value = ''
  bootstrapError.value = ''
  recentHistoryCount.value = 0
  pendingLiveLogs.length = 0
  primingHistory = false
}

async function loadRecentHistory() {
  loadingHistory.value = true
  bootstrapError.value = ''
  try {
    const response = await getLogHistory({
      before: 0,
      include_access: showAccessLogs.value,
      limit: 50,
    })
    logs.value = response.data.items.slice().reverse().map((item: LogItem) => toLogEntry(item))
    recentHistoryCount.value = logs.value.length
    await nextTick()
    logContainer.value?.scrollTo({ top: logContainer.value.scrollHeight })
  } catch (error) {
    bootstrapError.value = getErrorMessage(error, t('logs.historyLoadFailed'))
  } finally {
    loadingHistory.value = false
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

watch(showAccessLogs, enabled => {
  if (!enabled) {
    selectedSources.value = selectedSources.value.filter(source => source !== 'uvicorn.access')
  }
})

onMounted(() => {
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
  <PageScaffold dense full-height :title="t('logs.liveTitle')">
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

    <MetricStrip :items="metrics" compact />

    <Panel>
      <div class="logs-filter-grid">
        <div class="logs-search">
          <Search :size="16" />
          <Input
            v-model.trim="search"
            :aria-label="t('logs.search')"
            :placeholder="t('logs.search')"
          />
        </div>

        <label class="logs-switch">
          <Switch v-model="autoScroll" />
          <span>{{ t('logs.autoScroll') }}</span>
        </label>

        <label class="logs-switch">
          <Switch v-model="showAccessLogs" />
          <span>{{ t('logs.showAccessLogs') }}</span>
        </label>
      </div>

      <div class="logs-chip-filter">
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
    </Panel>

    <Alert v-if="bootstrapError" variant="default">
      <AlertDescription>{{ bootstrapError }}</AlertDescription>
    </Alert>

    <Panel class="logs-stream-panel" title="logs://live">
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
          class="logs-live-row"
        >
          <span class="logs-live-row__time">[{{ entry.timestamp.slice(11, 19) }}]</span>
          <StatusBadge :label="entry.level" :tone="logLevelTone(entry.level)" />
          <span class="logs-live-row__source">{{ entry.source }}</span>
          <span class="logs-live-row__message">{{ entry.message }}</span>
        </article>
      </div>
    </Panel>
  </PageScaffold>
</template>
