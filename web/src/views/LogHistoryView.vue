<template>
  <div class="page-view">
    <div class="page-header">
      <h1 class="page-title">{{ t('logs.historyTitle') }}</h1>
      <div class="page-actions">
        <v-btn
          :disabled="entries.length === 0"
          prepend-icon="mdi-download-outline"
          variant="text"
          @click="exportLogs"
        >
          {{ t('logs.export') }}
        </v-btn>
      </div>
    </div>

    <div class="page-summary-grid mb-4">
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('logs.totalRecords') }}</div>
        <div class="summary-card__value">{{ total }}</div>
      </v-sheet>
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('logs.visibleCount') }}</div>
        <div class="summary-card__value">{{ entries.length }}</div>
      </v-sheet>
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('logs.errorCount') }}</div>
        <div class="summary-card__value">{{ highSignalCount }}</div>
      </v-sheet>
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('logs.currentPage') }}</div>
        <div class="summary-card__value">{{ currentPage }} / {{ totalPages }}</div>
      </v-sheet>
    </div>

    <v-card class="page-panel history-query-card" rounded="xl">
      <div class="history-query-card__header">
        <div class="history-query-card__title">{{ t('logs.queryHistory') }}</div>
        <div class="history-query-card__actions">
          <v-btn
            :disabled="!hasPendingChanges || loading"
            :loading="loading"
            prepend-icon="mdi-magnify"
            @click="runQuery"
          >
            {{ t('logs.query') }}
          </v-btn>
          <v-btn
            :disabled="!hasAnyFilter || loading"
            variant="text"
            @click="resetFilters"
          >
            {{ t('logs.resetFilters') }}
          </v-btn>
        </div>
      </div>

      <div class="page-toolbar-form history-toolbar">
        <v-text-field
          v-model.trim="draftFilters.search"
          density="compact"
          hide-details
          :label="t('logs.search')"
          prepend-inner-icon="mdi-magnify"
          @keydown.enter.prevent="runQuery"
        />
        <v-select
          v-model="draftFilters.level"
          class="history-field"
          clearable
          density="compact"
          hide-details
          :items="levelOptions"
          :label="t('logs.level')"
        />
        <v-select
          v-model="draftFilters.source"
          class="history-field"
          clearable
          density="compact"
          hide-details
          :items="visibleSourceOptions"
          :label="t('logs.source')"
          :placeholder="t('logs.sourceHint')"
        />
        <v-text-field
          v-model="draftFilters.start"
          class="history-field"
          density="compact"
          hide-details
          :label="t('logs.startTime')"
          type="datetime-local"
        />
        <v-text-field
          v-model="draftFilters.end"
          class="history-field"
          density="compact"
          hide-details
          :label="t('logs.endTime')"
          type="datetime-local"
        />
      </div>

      <div class="history-presets">
        <v-switch
          v-model="showAccessLogs"
          class="history-presets__switch"
          color="primary"
          density="compact"
          hide-details
          inset
          :label="t('logs.showAccessLogs')"
        />
        <v-chip
          v-for="preset in timePresets"
          :key="preset.key"
          class="history-presets__chip"
          size="small"
          variant="tonal"
          @click="applyTimePreset(preset.hours)"
        >
          {{ t(preset.labelKey) }}
        </v-chip>
        <v-btn
          v-if="draftFilters.start || draftFilters.end"
          size="small"
          variant="text"
          @click="clearTimeRange"
        >
          {{ t('logs.clearTimeRange') }}
        </v-btn>
      </div>

      <v-alert
        v-if="validationMessage"
        class="mt-4"
        density="comfortable"
        type="warning"
        variant="tonal"
      >
        {{ validationMessage }}
      </v-alert>

      <div v-if="activeFilterChips.length > 0" class="history-active-filters">
        <v-chip
          v-for="chip in activeFilterChips"
          :key="chip.key"
          size="small"
          variant="tonal"
        >
          {{ chip.label }}
        </v-chip>
      </div>
    </v-card>

    <v-alert
      v-if="errorMessage"
      class="mb-4"
      density="comfortable"
      type="warning"
      variant="tonal"
    >
      {{ errorMessage }}
    </v-alert>

    <v-card class="page-panel log-card">
      <div class="history-result-bar">
        <span>{{ resultsLabel }}</span>
      </div>

      <div v-if="entries.length === 0" class="text-medium-emphasis text-center pa-8">
        {{ loading ? t('common.loading') : t('logs.noHistory') }}
      </div>

      <div
        v-else
        ref="listContainer"
        class="history-list-shell"
      >
        <div
          v-for="entry in entries"
          :key="entry.id"
          class="history-list-item"
          :class="{ 'history-list-item--active': selectedEntryId === entry.id }"
        >
          <button
            class="history-list-row"
            type="button"
            @click="selectEntry(entry.id)"
          >
            <span class="history-list-row__level">
              <v-chip
                class="history-list-row__level-chip"
                :color="levelColor(entry.level)"
                size="small"
                variant="tonal"
              >
                {{ entry.level }}
              </v-chip>
            </span>
            <span class="history-list-row__source">{{ entry.source }}</span>
            <span class="history-list-row__time">{{ entry.timestamp }}</span>
            <span class="history-list-row__message">{{ entry.message }}</span>
          </button>

          <div v-if="selectedEntryId === entry.id" class="history-detail-panel">
            <div class="history-detail-panel__meta">
              <v-chip
                class="history-list-row__level-chip"
                :color="levelColor(entry.level)"
                size="small"
                variant="tonal"
              >
                {{ entry.level }}
              </v-chip>
              <span class="history-detail-panel__source">{{ entry.source }}</span>
              <span class="history-detail-panel__time">{{ entry.timestamp }}</span>
            </div>
            <div class="history-detail-panel__message">{{ entry.message }}</div>
            <pre class="history-log-card__raw">{{ entry.raw }}</pre>
            <pre v-if="Object.keys(entry.extra).length > 0" class="history-log-card__raw">{{ JSON.stringify(entry.extra, null, 2) }}</pre>
          </div>
        </div>
      </div>

      <div class="history-pagination">
        <span class="history-pagination__status">
          {{ t('logs.paginationStatus', { page: currentPage, totalPages, total }) }}
        </span>
        <div class="history-pagination__actions">
          <v-btn
            :disabled="loading || !canGoPrev"
            variant="text"
            @click="goToPage(1)"
          >
            {{ t('logs.firstPage') }}
          </v-btn>
          <v-btn
            :disabled="loading || !canGoPrev"
            variant="text"
            @click="goToPage(currentPage - 1)"
          >
            {{ t('logs.prevPage') }}
          </v-btn>
          <v-btn
            :disabled="loading || !canGoNext"
            variant="tonal"
            @click="goToPage(currentPage + 1)"
          >
            {{ t('logs.nextPage') }}
          </v-btn>
          <v-btn
            :disabled="loading || !canGoNext"
            variant="text"
            @click="goToPage(totalPages)"
          >
            {{ t('logs.lastPage') }}
          </v-btn>
        </div>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
  import type { LogHistoryQuery, LogItem } from '@/api/logs'
  import axios from 'axios'
  import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import { getErrorMessage } from '@/api/client'
  import { getLogHistory, getLogSources } from '@/api/logs'

  interface HistoryLogEntry extends LogItem {
    id: string
  }

  interface FiltersState {
    search: string
    level: string | null
    source: string
    start: string
    end: string
  }

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
    search: '',
    level: null,
    source: '',
    start: '',
    end: '',
  })
  const appliedFilters = ref<FiltersState>({
    search: '',
    level: null,
    source: '',
    start: '',
    end: '',
  })
  const entries = ref<HistoryLogEntry[]>([])
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
    entries.value.filter(entry => entry.level === 'ERROR' || entry.level === 'CRITICAL' || entry.level === 'WARNING').length,
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
  const hasAnyFilter = computed(() => {
    const values = [
      draftFilters.search,
      draftFilters.level,
      draftFilters.source,
      draftFilters.start,
      draftFilters.end,
    ]
    return values.some(Boolean) || showAccessLogs.value
  })
  const hasPendingChanges = computed(() =>
    JSON.stringify(draftFilters) !== JSON.stringify(appliedFilters.value)
    || showAccessLogs.value !== appliedShowAccessLogs.value,
  )
  const activeFilterChips = computed(() => {
    const chips: Array<{ key: string, label: string }> = []
    if (appliedFilters.value.search) {
      chips.push({ key: 'search', label: `${t('logs.search')}: ${appliedFilters.value.search}` })
    }
    if (appliedFilters.value.level) {
      chips.push({ key: 'level', label: `${t('logs.level')}: ${appliedFilters.value.level}` })
    }
    if (appliedFilters.value.source) {
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
  const visibleSourceOptions = computed(() =>
    sourceOptions.value.filter(item => showAccessLogs.value || item !== 'uvicorn.access'),
  )
  const resultsLabel = computed(() => {
    if (loading.value && entries.value.length === 0) {
      return t('common.loading')
    }
    if (entries.value.length === 0) {
      return t('logs.noHistory')
    }
    return t('logs.resultsLoaded', { count: entries.value.length })
  })

  function cloneFilters (filters: FiltersState): FiltersState {
    return {
      search: filters.search,
      level: filters.level,
      source: filters.source,
      start: filters.start,
      end: filters.end,
    }
  }

  function toHistoryEntry (item: LogItem): HistoryLogEntry {
    return {
      ...item,
      id: `${item.timestamp}_${item.level}_${item.source}_${Math.random().toString(16).slice(2)}`,
    }
  }

  function readFiltersFromRoute (): FiltersState {
    const query = route.query
    return {
      search: typeof query.search === 'string' ? query.search : '',
      level: typeof query.level === 'string' ? query.level : null,
      source: typeof query.source === 'string' ? query.source : '',
      start: typeof query.start === 'string' ? query.start : '',
      end: typeof query.end === 'string' ? query.end : '',
    }
  }

  async function syncRouteQuery (filters: FiltersState) {
    const nextQuery: Record<string, string> = {}
    if (filters.search) nextQuery.search = filters.search
    if (filters.level) nextQuery.level = filters.level
    if (filters.source) nextQuery.source = filters.source
    if (filters.start) nextQuery.start = filters.start
    if (filters.end) nextQuery.end = filters.end
    await router.replace({ query: nextQuery })
  }

  function buildQuery (before = 0): LogHistoryQuery {
    return {
      before,
      limit: PAGE_SIZE,
      level: appliedFilters.value.level || undefined,
      source: appliedFilters.value.source || undefined,
      search: appliedFilters.value.search || undefined,
      start: appliedFilters.value.start || undefined,
      end: appliedFilters.value.end || undefined,
      include_access: appliedShowAccessLogs.value,
    }
  }

  async function fetchHistory (before = 0) {
    activeHistoryRequest?.abort()
    activeHistoryRequest = new AbortController()
    const currentRequest = activeHistoryRequest
    loading.value = true
    errorMessage.value = ''

    try {
      const response = await getLogHistory(buildQuery(before), currentRequest.signal)
      entries.value = response.data.items.map(item => toHistoryEntry(item))
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

  async function runQuery () {
    clearAutoQueryTimer()
    if (validationMessage.value) {
      return
    }
    if (!showAccessLogs.value && draftFilters.source === 'uvicorn.access') {
      draftFilters.source = ''
    }
    appliedFilters.value = cloneFilters(draftFilters)
    appliedShowAccessLogs.value = showAccessLogs.value
    await syncRouteQuery(appliedFilters.value)
    await fetchHistory(0)
  }

  async function resetFilters () {
    clearAutoQueryTimer()
    draftFilters.search = ''
    draftFilters.level = null
    draftFilters.source = ''
    draftFilters.start = ''
    draftFilters.end = ''
    showAccessLogs.value = false
    appliedFilters.value = cloneFilters(draftFilters)
    appliedShowAccessLogs.value = showAccessLogs.value
    await syncRouteQuery(appliedFilters.value)
    await fetchHistory(0)
  }

  function goToPage (page: number) {
    const nextPage = Math.min(Math.max(page, 1), totalPages.value)
    if (nextPage === currentPage.value) {
      return
    }
    void fetchHistory((nextPage - 1) * PAGE_SIZE)
  }

  function selectEntry (id: string) {
    selectedEntryId.value = selectedEntryId.value === id ? '' : id
  }

  function levelColor (level: string) {
    if (level === 'ERROR' || level === 'CRITICAL') return 'error'
    if (level === 'WARNING') return 'warning'
    if (level === 'SUCCESS') return 'success'
    return 'info'
  }

  function formatDateTimeLocal (value: Date) {
    const year = value.getFullYear()
    const month = `${value.getMonth() + 1}`.padStart(2, '0')
    const day = `${value.getDate()}`.padStart(2, '0')
    const hours = `${value.getHours()}`.padStart(2, '0')
    const minutes = `${value.getMinutes()}`.padStart(2, '0')
    return `${year}-${month}-${day}T${hours}:${minutes}`
  }

  function formatDateTimeLabel (value: string) {
    return value.replace('T', ' ')
  }

  function applyTimePreset (hours: number) {
    const end = new Date()
    const start = new Date(end.getTime() - hours * 60 * 60 * 1000)
    draftFilters.start = formatDateTimeLocal(start)
    draftFilters.end = formatDateTimeLocal(end)
  }

  function clearTimeRange () {
    draftFilters.start = ''
    draftFilters.end = ''
  }

  function clearAutoQueryTimer () {
    if (autoQueryTimer !== null) {
      clearTimeout(autoQueryTimer)
      autoQueryTimer = null
    }
  }

  function scheduleAutoQuery () {
    clearAutoQueryTimer()
    if (validationMessage.value || !hasPendingChanges.value) {
      return
    }
    autoQueryTimer = window.setTimeout(() => {
      autoQueryTimer = null
      void runQuery()
    }, 3000)
  }

  function exportLogs () {
    const blob = new Blob(
      [entries.value.map(entry => JSON.stringify(entry)).join('\n')],
      { type: 'application/jsonl;charset=utf-8' },
    )
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `apeiria-history-logs-${Date.now()}.jsonl`
    link.click()
    URL.revokeObjectURL(url)
  }

  watch(() => route.query, query => {
    clearAutoQueryTimer()
    const nextFilters = {
      search: typeof query.search === 'string' ? query.search : '',
      level: typeof query.level === 'string' ? query.level : null,
      source: typeof query.source === 'string' ? query.source : '',
      start: typeof query.start === 'string' ? query.start : '',
      end: typeof query.end === 'string' ? query.end : '',
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
    () => {
      scheduleAutoQuery()
    },
  )

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

  watch(showAccessLogs, enabled => {
    clearAutoQueryTimer()
    if (!enabled && draftFilters.source === 'uvicorn.access') {
      draftFilters.source = ''
    }
    scheduleAutoQuery()
  })

  onBeforeUnmount(() => {
    clearAutoQueryTimer()
    activeHistoryRequest?.abort()
  })
</script>

<style scoped>
.history-query-card {
  margin-bottom: 16px;
  padding: 18px;
  background:
    linear-gradient(135deg, rgba(var(--v-theme-primary), 0.05), transparent 40%),
    rgb(var(--v-theme-surface-container-low));
}

.history-query-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.history-query-card__title {
  font-size: 1rem;
  font-weight: 700;
}

.history-query-card__actions {
  display: flex;
  gap: 8px;
}

.history-toolbar {
  align-items: center;
}

.history-field {
  min-width: 180px;
}

.history-presets {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.history-presets__chip {
  cursor: pointer;
}

.history-active-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.log-card {
  background: rgb(var(--v-theme-surface-container-low));
  min-height: 60vh;
}

.history-result-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 16px 20px 8px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.88rem;
}

.history-list-shell {
  display: flex;
  flex-direction: column;
  height: min(68vh, 1320px);
  min-height: 620px;
  overflow-y: auto;
  padding: 0 20px 16px;
}

.history-list-item {
  border-bottom: 1px solid rgba(var(--v-theme-outline-variant), 0.24);
  background:
    linear-gradient(135deg, rgba(var(--v-theme-primary), 0.05), transparent 55%),
    rgba(var(--v-theme-surface), 0.58);
  transition:
    background var(--motion-base) var(--motion-ease),
    box-shadow var(--motion-base) var(--motion-ease);
}

.history-list-item:hover {
  background:
    linear-gradient(135deg, rgba(var(--v-theme-primary), 0.08), transparent 55%),
    rgba(var(--v-theme-surface), 0.68);
}

.history-list-item--active {
  background:
    linear-gradient(135deg, rgba(var(--v-theme-primary), 0.12), transparent 55%),
    rgba(var(--v-theme-surface), 0.8);
}

.history-list-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 14px 16px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    background var(--motion-base) var(--motion-ease),
    box-shadow var(--motion-base) var(--motion-ease);
}

.history-list-row:hover {
  background: rgba(var(--v-theme-primary), 0.04);
}

.history-list-row:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.history-list-row__level {
  flex: 0 0 88px;
}

.history-list-row__level-chip {
  width: 80px;
  justify-content: center;
  font-weight: 700;
}

.history-list-row__source,
.history-list-row__time {
  font-family: var(--font-family-mono);
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.66);
  white-space: nowrap;
}

.history-list-row__source {
  flex: 0 0 140px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-list-row__time {
  flex: 0 0 180px;
}

.history-list-row__message {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}

.history-detail-panel {
  margin: 0 16px 14px;
  padding: 14px 16px;
  border-radius: var(--shape-large);
  background: rgba(var(--v-theme-on-surface), 0.05);
  border: 1px solid rgba(var(--v-theme-outline-variant), 0.28);
}

.history-detail-panel__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.history-detail-panel__source,
.history-detail-panel__time {
  font-family: var(--font-family-mono);
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.66);
}

.history-detail-panel__message {
  margin-bottom: 12px;
  font-weight: 600;
  white-space: pre-wrap;
  word-break: break-word;
}

.history-log-card__raw {
  margin: 0 0 8px;
  padding: 12px;
  border-radius: var(--shape-base);
  background: rgba(var(--v-theme-on-surface), 0.05);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-family-mono);
  font-size: 12px;
}

.history-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin: 0 20px 20px;
  padding: 16px 20px;
  border-radius: var(--shape-2xlarge);
  background: rgba(var(--v-theme-surface), 0.72);
  backdrop-filter: blur(10px);
}

.history-pagination__status {
  color: rgba(var(--v-theme-on-surface), 0.74);
}

.history-pagination__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 960px) {
  .history-query-card__header,
  .history-result-bar,
  .history-pagination {
    flex-direction: column;
    align-items: stretch;
  }

  .history-query-card__actions,
  .history-pagination__actions {
    justify-content: flex-end;
    flex-wrap: wrap;
  }

  .history-list-row {
    display: grid;
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .history-list-row__level,
  .history-list-row__source,
  .history-list-row__time {
    flex: none;
  }

  .history-list-row__message {
    white-space: normal;
  }
}
</style>
