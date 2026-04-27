<template>
  <div class="page-view">
    <div class="page-header">
      <h1 class="page-title">{{ t('logs.liveTitle') }}</h1>
      <div class="page-actions">
        <v-chip :color="connected ? 'success' : 'error'" size="small" variant="tonal">
          {{ connected ? t('logs.connected') : t('logs.disconnected') }}
        </v-chip>
        <v-btn
          :prepend-icon="connected ? 'mdi-lan-disconnect' : 'mdi-connection'"
          size="small"
          variant="text"
          @click="toggleConnection"
        >
          {{ connected ? t('logs.disconnect') : t('logs.connect') }}
        </v-btn>
        <v-btn
          :disabled="filteredLogs.length === 0"
          prepend-icon="mdi-download-outline"
          size="small"
          variant="text"
          @click="exportLogs"
        >
          {{ t('logs.export') }}
        </v-btn>
        <v-btn
          :disabled="logs.length === 0"
          prepend-icon="mdi-delete-sweep"
          size="small"
          variant="text"
          @click="clearLogs"
        >
          {{ t('logs.clear') }}
        </v-btn>
      </div>
    </div>

    <div class="page-toolbar-form live-toolbar">
      <v-text-field
        v-model.trim="search"
        density="compact"
        hide-details
        :label="t('logs.search')"
        prepend-inner-icon="mdi-magnify"
      />
      <v-select
        v-model="selectedLevels"
        chips
        class="logs-filter"
        density="compact"
        hide-details
        :items="levelOptions"
        :label="t('logs.level')"
        multiple
      />
      <v-select
        v-model="selectedSources"
        chips
        class="logs-filter"
        density="compact"
        hide-details
        :items="sourceOptions"
        :label="t('logs.source')"
        multiple
      />
      <v-switch
        v-model="autoScroll"
        color="primary"
        hide-details
        inset
        :label="t('logs.autoScroll')"
      />
      <v-switch
        v-model="showAccessLogs"
        color="primary"
        hide-details
        inset
        :label="t('logs.showAccessLogs')"
      />
    </div>

    <v-alert
      v-if="bootstrapError"
      class="mb-4"
      density="comfortable"
      type="warning"
      variant="tonal"
    >
      {{ bootstrapError }}
    </v-alert>

    <v-card class="page-panel live-log-viewer">
      <div class="live-log-viewer__head">
        <div class="live-log-viewer__dots">
          <span />
          <span />
          <span />
        </div>
        <span class="live-log-viewer__title">logs://live</span>
      </div>

      <div v-if="filteredLogs.length === 0" class="text-medium-emphasis text-center pa-8">
        {{ loadingHistory ? t('common.loading') : t('logs.waiting') }}
      </div>

      <div v-else ref="logContainer" class="live-log-stream">
        <div
          v-for="entry in filteredLogs"
          :key="entry.id"
          class="live-log-row"
        >
          <span class="live-log-row__time">[{{ entry.timestamp.slice(11) }}]</span>
          <span class="live-log-row__level" :class="`live-log-row__level--${entry.level.toLowerCase()}`">
            {{ entry.level }}
          </span>
          <span class="live-log-row__source">{{ entry.source }}</span>
          <span class="live-log-row__message">{{ entry.message }}</span>
        </div>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
  import type { LogItem } from '@/api/logs'
  import { computed, nextTick, onActivated, onDeactivated, onMounted, onUnmounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { getErrorMessage } from '@/api/client'
  import { getLogHistory } from '@/api/logs'

  interface LogEntry {
    id: string
    timestamp: string
    level: string
    source: string
    message: string
    raw: string
    extra: Record<string, unknown>
  }

  const logs = ref<LogEntry[]>([])
  const connected = ref(false)
  const autoScroll = ref(true)
  const search = ref('')
  const selectedLevels = ref<string[]>([])
  const selectedSources = ref<string[]>([])
  const showAccessLogs = ref(false)
  const logContainer = ref<HTMLElement>()
  const loadingHistory = ref(false)
  const bootstrapError = ref('')
  const recentHistoryCount = ref(0)
  const { t } = useI18n()
  let ws: WebSocket | null = null
  let primingHistory = false
  const pendingLiveLogs: LogEntry[] = []
  const MAX_LIVE_LOGS = 500

  const levelOptions = computed(() => Array.from(new Set(logs.value.map(item => item.level))).toSorted())
  const sourceOptions = computed(() => Array.from(new Set(logs.value
    .filter(item => showAccessLogs.value || item.source !== 'uvicorn.access')
    .map(item => item.source))).toSorted())
  const filteredLogs = computed(() => logs.value.filter(entry => {
    if (!showAccessLogs.value && entry.source === 'uvicorn.access') {
      return false
    }
    if (selectedLevels.value.length > 0 && !selectedLevels.value.includes(entry.level)) {
      return false
    }
    if (selectedSources.value.length > 0 && !selectedSources.value.includes(entry.source)) {
      return false
    }
    const keyword = search.value.trim().toLowerCase()
    if (!keyword) {
      return true
    }
    const haystack = `${entry.timestamp} ${entry.level} ${entry.source} ${entry.message} ${entry.raw} ${JSON.stringify(entry.extra)}`.toLowerCase()
    return haystack.includes(keyword)
  }))

  function connect () {
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
      const entry = normalizeLogFrame(event.data)
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

  function disconnect () {
    ws?.close()
    ws = null
    connected.value = false
  }

  function clearLogs () {
    logs.value = []
    recentHistoryCount.value = 0
  }

  function resetLogsView () {
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

  function toLogEntry (item: LogItem): LogEntry {
    return {
      timestamp: item.timestamp,
      level: item.level,
      source: item.source,
      message: item.message,
      raw: item.raw,
      extra: item.extra,
      id: `${item.timestamp}_${item.level}_${item.source}_${Math.random().toString(16).slice(2)}`,
    }
  }

  async function loadRecentHistory () {
    loadingHistory.value = true
    bootstrapError.value = ''
    try {
      const response = await getLogHistory({
        before: 0,
        limit: 50,
        include_access: showAccessLogs.value,
      })
      logs.value = response.data.items.toReversed().map(item => toLogEntry(item))
      recentHistoryCount.value = logs.value.length
      await nextTick()
      logContainer.value?.scrollTo({ top: logContainer.value.scrollHeight })
    } catch (error) {
      bootstrapError.value = getErrorMessage(error, t('logs.historyLoadFailed'))
    } finally {
      loadingHistory.value = false
    }
  }

  async function initializeLogsView () {
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

  async function toggleConnection () {
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

  function normalizeLogFrame (frame: string): LogEntry {
    try {
      const parsed = JSON.parse(frame) as Partial<LogEntry>
      return {
        id: `${parsed.timestamp || Date.now()}_${Math.random().toString(16).slice(2)}`,
        timestamp: parsed.timestamp || new Date().toISOString(),
        level: parsed.level || 'INFO',
        source: parsed.source || 'unknown',
        message: parsed.message || parsed.raw || frame,
        raw: parsed.raw || frame,
        extra: (parsed.extra && typeof parsed.extra === 'object') ? parsed.extra as Record<string, unknown> : {},
      }
    } catch {
      return {
        id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
        timestamp: new Date().toISOString(),
        level: 'INFO',
        source: 'legacy',
        message: frame,
        raw: frame,
        extra: {},
      }
    }
  }

  function buildLogKey (entry: Pick<LogEntry, 'timestamp' | 'level' | 'source' | 'raw'>) {
    return `${entry.timestamp}|${entry.level}|${entry.source}|${entry.raw}`
  }

  function flushPendingLiveLogs () {
    const existingKeys = new Set(logs.value.map(item => buildLogKey(item)))
    for (const entry of pendingLiveLogs.splice(0)) {
      const entryKey = buildLogKey(entry)
      if (existingKeys.has(entryKey)) {
        continue
      }
      existingKeys.add(entryKey)
      appendLiveLog(entry)
    }
    scrollToBottomIfNeeded()
  }

  function appendLiveLog (entry: LogEntry) {
    logs.value.push(entry)
    const maxLogs = recentHistoryCount.value + MAX_LIVE_LOGS
    if (logs.value.length <= maxLogs) {
      return
    }
    logs.value.splice(recentHistoryCount.value, logs.value.length - maxLogs)
  }

  function scrollToBottomIfNeeded () {
    if (!autoScroll.value) {
      return
    }
    nextTick(() => {
      logContainer.value?.scrollTo(0, logContainer.value.scrollHeight)
    })
  }

  function exportLogs () {
    const blob = new Blob(
      [filteredLogs.value.map(entry => JSON.stringify(entry)).join('\n')],
      { type: 'application/jsonl;charset=utf-8' },
    )
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `apeiria-live-logs-${Date.now()}.jsonl`
    link.click()
    URL.revokeObjectURL(url)
  }

  onMounted(() => {
    void initializeLogsView()
  })
  watch(showAccessLogs, enabled => {
    if (enabled) {
      return
    }
    selectedSources.value = selectedSources.value.filter(source => source !== 'uvicorn.access')
  })
  onActivated(() => {
    if (!connected.value) {
      void initializeLogsView()
    }
  })
  onDeactivated(disconnect)
  onUnmounted(disconnect)
</script>

<style scoped>
.live-toolbar {
  margin-bottom: 16px;
}

.logs-filter {
  min-width: 180px;
}

.live-log-viewer {
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(var(--v-theme-primary), 0.05), transparent 40%),
    rgb(var(--v-theme-surface-container-low));
}

.live-log-viewer__head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(var(--v-theme-outline-variant), 0.3);
  background: rgba(var(--v-theme-on-surface), 0.05);
}

.live-log-viewer__dots {
  display: flex;
  gap: 6px;
}

.live-log-viewer__dots span {
  width: 10px;
  height: 10px;
  border-radius: var(--shape-pill);
  background: rgba(var(--v-theme-on-surface), 0.3);
}

.live-log-viewer__dots span:nth-child(1) {
  background: rgb(var(--v-theme-error));
}

.live-log-viewer__dots span:nth-child(2) {
  background: rgb(var(--v-theme-warning));
}

.live-log-viewer__dots span:nth-child(3) {
  background: rgb(var(--v-theme-success));
}

.live-log-viewer__title {
  font-family: var(--font-family-mono);
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.live-log-stream {
  max-height: 72vh;
  overflow-y: auto;
  padding: 12px 16px 16px;
}

.live-log-row {
  display: grid;
  grid-template-columns: 92px 76px 180px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  padding: 6px 0;
  font-family: var(--font-family-mono);
  font-size: 0.94rem;
  line-height: 1.55;
}

.live-log-row__time,
.live-log-row__source {
  color: rgba(var(--v-theme-on-surface), 0.64);
}

.live-log-row__level {
  display: inline-flex;
  justify-content: center;
  min-width: 64px;
  padding: 1px 8px;
  border-radius: var(--shape-xsmall);
  font-size: 0.78rem;
  font-weight: 700;
}

.live-log-row__level--info {
  background: rgba(var(--v-theme-info), 0.18);
  color: rgb(var(--v-theme-info));
}

.live-log-row__level--warning {
  background: rgba(var(--v-theme-warning), 0.18);
  color: rgb(var(--v-theme-warning));
}

.live-log-row__level--error,
.live-log-row__level--critical {
  background: rgba(var(--v-theme-error), 0.18);
  color: rgb(var(--v-theme-error));
}

.live-log-row__level--success {
  background: rgba(var(--v-theme-success), 0.18);
  color: rgb(var(--v-theme-success));
}

.live-log-row__message {
  min-width: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 960px) {
  .live-log-row {
    grid-template-columns: 1fr;
    gap: 4px;
    padding: 10px 0;
  }
}
</style>
