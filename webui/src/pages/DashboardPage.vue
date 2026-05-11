<script setup lang="ts">
import type {
  DashboardEventItem,
  DashboardStatus,
  WebUIBuildStatus,
} from '@/api/dashboard'
import type { WorkbenchMetricItem, WorkbenchTone } from '@/components/management'
import {
  AlertCircle,
  Cable,
  CheckCircle2,
  Clock3,
  History,
  Plug,
  Puzzle,
  RefreshCw,
  ShieldCheck,
  TerminalSquare,
  Users,
} from 'lucide-vue-next'
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import {
  getDashboardEvents,
  getStatus,
  getWebUIBuildStatus,
  streamRebuildWebUI,
} from '@/api/dashboard'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  EmptyState,
  MetricStrip,
  PageScaffold,
  Panel,
  StatusBadge,
} from '@/components/management'
import { useRestartController } from '@/composables/useRestartController'
import { useNoticeStore } from '@/stores/notice'

const status = ref<DashboardStatus | null>(null)
const recentEvents = ref<DashboardEventItem[]>([])
const webuiBuildStatus = ref<WebUIBuildStatus | null>(null)
const loading = ref(false)
const dashboardError = ref('')
const rebuildingWebUI = ref(false)
const buildDialogVisible = ref(false)
const buildLogs = ref('')
const buildDialogStatus = ref('')
const buildLogCardRef = ref<HTMLElement | null>(null)
const { t } = useI18n()
const noticeStore = useNoticeStore()
const { restarting, restartAndReload } = useRestartController()
let refreshTimer: number | null = null

const statusTone = computed<WorkbenchTone>(() =>
  status.value?.status === 'running' ? 'success' : 'warning',
)

const dashboardMetrics = computed<WorkbenchMetricItem[]>(() => [
  {
    key: 'status',
    label: t('dashboard.status'),
    value: status.value?.status || '...',
    icon: status.value?.status === 'running' ? CheckCircle2 : AlertCircle,
    tone: statusTone.value,
  },
  {
    key: 'uptime',
    label: t('dashboard.uptime'),
    value: formatUptime(status.value?.uptime),
    icon: Clock3,
  },
  {
    key: 'plugins',
    label: t('dashboard.plugins'),
    value: status.value?.plugins_count ?? '...',
    icon: Puzzle,
  },
  {
    key: 'adapters',
    label: t('dashboard.adapters'),
    value: status.value?.adapters?.length ?? '...',
    icon: Cable,
    tone: 'info',
  },
])

const dashboardSecondaryMetrics = computed<WorkbenchMetricItem[]>(() => [
  {
    key: 'disabled-plugins',
    label: t('dashboard.disabledPlugins'),
    value: status.value?.disabled_plugins_count ?? '...',
    icon: Plug,
    tone: 'warning',
  },
  {
    key: 'groups',
    label: t('dashboard.groups'),
    value: status.value?.groups_count ?? '...',
    icon: Users,
  },
  {
    key: 'disabled-groups',
    label: t('dashboard.disabledGroups'),
    value: status.value?.disabled_groups_count ?? '...',
    icon: Users,
    tone: 'warning',
  },
  {
    key: 'access-rules',
    label: t('dashboard.accessRules'),
    value: status.value?.access_rules_count ?? '...',
    icon: ShieldCheck,
    tone: 'info',
  },
])

const webuiBuildHeadline = computed(() => {
  if (!webuiBuildStatus.value) {
    return ''
  }
  if (!webuiBuildStatus.value.is_built) {
    return t('dashboard.webuiBuildMissing')
  }
  return t('dashboard.webuiBuildOutdated')
})

const webuiBuildDescription = computed(() => {
  if (!webuiBuildStatus.value) {
    return ''
  }
  if (!webuiBuildStatus.value.can_build) {
    return t('dashboard.webuiBuildUnavailable')
  }
  return t('dashboard.webuiBuildDetail', {
    tool: webuiBuildStatus.value.build_tool || 'pnpm',
  })
})

const showWebUIBuildCard = computed(() =>
  Boolean(
    webuiBuildStatus.value
    && (!webuiBuildStatus.value.is_built || webuiBuildStatus.value.is_stale),
  ),
)

async function refreshDashboard(options: { silent?: boolean } = {}) {
  loading.value = true
  try {
    const [statusResponse, eventsResponse, buildStatusResponse] = await Promise.all([
      getStatus(),
      getDashboardEvents(),
      getWebUIBuildStatus(),
    ])
    status.value = statusResponse.data
    recentEvents.value = eventsResponse.data.items
    webuiBuildStatus.value = buildStatusResponse.data
    dashboardError.value = ''
  } catch (error) {
    dashboardError.value = getErrorMessage(error, t('dashboard.refreshFailed'))
    if (!options.silent) {
      noticeStore.show(dashboardError.value, 'error')
    }
  } finally {
    loading.value = false
  }
}

async function handleRebuildWebUI() {
  buildDialogVisible.value = true
  buildLogs.value = ''
  buildDialogStatus.value = t('dashboard.webuiBuildRunning')
  rebuildingWebUI.value = true
  try {
    let buildSucceeded = false
    let buildFailedMessage = ''

    await streamRebuildWebUI(async event => {
      if (event.event === 'chunk') {
        appendBuildLogs(event.chunk || '')
        return
      }

      if (event.event === 'error') {
        buildFailedMessage = event.detail || t('dashboard.webuiBuildFailed')
        return
      }

      if (event.event === 'done' && event.status) {
        buildSucceeded = true
        webuiBuildStatus.value = event.status
      }
    })

    if (!buildSucceeded) {
      throw new Error(buildFailedMessage || t('dashboard.webuiBuildFailed'))
    }

    rebuildingWebUI.value = false
    noticeStore.show(t('dashboard.webuiBuildUpdated'), 'success')
    buildDialogStatus.value = t('dashboard.webuiBuildUpdated')
    await waitForWebUIBuildRefresh()
  } catch (error) {
    const message = getErrorMessage(error, t('dashboard.webuiBuildFailed'))
    if (!buildLogs.value.trim()) {
      buildLogs.value = message
    } else if (!buildLogs.value.includes(message)) {
      appendBuildLogs(`\n${message}\n`)
    }
    buildDialogStatus.value = t('dashboard.webuiBuildFailed')
    noticeStore.show(message, 'error')
  } finally {
    rebuildingWebUI.value = false
  }
}

function appendBuildLogs(chunk: string) {
  buildLogs.value += chunk
  void nextTick(() => {
    const container = buildLogCardRef.value
    if (!container) {
      return
    }
    container.scrollTop = container.scrollHeight
  })
}

async function waitForWebUIBuildRefresh() {
  for (let attempt = 0; attempt < 15; attempt += 1) {
    try {
      const response = await getWebUIBuildStatus()
      webuiBuildStatus.value = response.data
      if (response.data.is_built && !response.data.is_stale) {
        await sleep(3000)
        window.location.reload()
        return
      }
    } catch {
      // Ignore transient polling failures while waiting for the new assets.
    }
    await sleep(1000)
  }
}

async function handleRestart() {
  if (!window.confirm(t('dashboard.restartConfirm'))) {
    return
  }
  await restartAndReload()
}

function sleep(ms: number) {
  return new Promise(resolve => window.setTimeout(resolve, ms))
}

function formatUptime(seconds?: number): string {
  if (!seconds) {
    return '...'
  }
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}

function eventTone(level: string): WorkbenchTone {
  if (level === 'ERROR' || level === 'CRITICAL') {
    return 'error'
  }
  if (level === 'WARNING') {
    return 'warning'
  }
  return 'info'
}

function startAutoRefresh() {
  stopAutoRefresh()
  refreshTimer = window.setInterval(() => {
    void refreshDashboard({ silent: true })
  }, 15_000)
}

function stopAutoRefresh() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onMounted(() => {
  void refreshDashboard()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<template>
  <PageScaffold
    :error-message="dashboardError"
    :kicker="t('layout.brand')"
    :subtitle="t('dashboard.description')"
    :title="t('dashboard.title')"
  >
    <template #actions>
      <Button :disabled="restarting" variant="outline" @click="handleRestart">
        <RefreshCw :size="16" />
        {{ t('dashboard.restart') }}
      </Button>

      <Button :disabled="loading" variant="secondary" @click="refreshDashboard()">
        <RefreshCw :class="{ 'animate-spin': loading }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <Alert v-if="showWebUIBuildCard" class="dashboard-build-alert">
      <TerminalSquare :size="18" />
      <AlertTitle>{{ webuiBuildHeadline }}</AlertTitle>
      <AlertDescription class="dashboard-build-alert__body">
        <span>{{ webuiBuildDescription }}</span>
        <Button
          :disabled="!webuiBuildStatus?.can_build || rebuildingWebUI"
          size="sm"
          variant="secondary"
          @click="handleRebuildWebUI"
        >
          {{ t('dashboard.rebuildWebUI') }}
        </Button>
      </AlertDescription>
    </Alert>

    <MetricStrip :items="dashboardMetrics" />

    <section class="dashboard-grid">
      <Panel class="dashboard-adapters-panel" :title="t('dashboard.adapterList')">
        <div v-if="status?.adapters?.length" class="dashboard-adapter-list">
          <StatusBadge
            v-for="adapter in status.adapters"
            :key="adapter"
            :label="adapter"
            tone="info"
          />
        </div>
        <EmptyState
          v-else
          :text="t('dashboard.noAdaptersText')"
          :title="t('dashboard.noAdapters')"
        />
      </Panel>

      <div class="dashboard-side-metrics">
        <h2>{{ t('dashboard.extraStats') }}</h2>
        <MetricStrip compact :items="dashboardSecondaryMetrics" />
      </div>
    </section>

    <Panel :title="t('dashboard.recentEvents')">
      <EmptyState
        v-if="recentEvents.length === 0"
        :icon="History"
        :title="t('dashboard.noEvents')"
      />

      <div v-else class="dashboard-events-list">
        <article
          v-for="event in recentEvents"
          :key="`${event.timestamp}:${event.source}:${event.message}`"
          class="dashboard-event"
        >
          <StatusBadge :label="event.level" :tone="eventTone(event.level)" />
          <div class="dashboard-event__content">
            <div class="dashboard-event__title">
              {{ event.message }}
            </div>
            <div class="dashboard-event__meta">
              <span>{{ event.timestamp }}</span>
              <span>{{ t('dashboard.eventSource') }}: {{ event.source }}</span>
            </div>
          </div>
        </article>
      </div>
    </Panel>

    <Dialog v-model:open="buildDialogVisible">
      <DialogContent class="dashboard-build-dialog">
        <DialogHeader>
          <DialogTitle>{{ t('dashboard.rebuildWebUI') }}</DialogTitle>
          <DialogDescription>{{ buildDialogStatus }}</DialogDescription>
        </DialogHeader>

        <div v-if="rebuildingWebUI" class="workbench-progress" />

        <div ref="buildLogCardRef" class="dashboard-build-log">
          <pre>{{ buildLogs || t('dashboard.webuiBuildWaiting') }}</pre>
        </div>

        <DialogFooter>
          <Button
            :disabled="rebuildingWebUI"
            variant="secondary"
            @click="buildDialogVisible = false"
          >
            {{ t('common.close') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </PageScaffold>
</template>
