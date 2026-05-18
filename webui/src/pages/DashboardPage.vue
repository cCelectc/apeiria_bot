<script setup lang="ts">
import type {
  DashboardEventItem,
  DashboardStatus,
  WebUIBuildStatus,
} from '@/api/dashboard'
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useRestartController } from '@/composables/useRestartController'
import { useNoticeStore } from '@/stores/notice'

type DashboardTone = 'default' | 'destructive' | 'outline' | 'secondary'
type DashboardStat = {
  key: string
  label: string
  value: number | string
  icon: typeof AlertCircle
  variant?: DashboardTone
}

const status = ref<DashboardStatus | null>(null)
const recentEvents = ref<DashboardEventItem[]>([])
const webuiBuildStatus = ref<WebUIBuildStatus | null>(null)
const loading = ref(false)
const dashboardError = ref('')
const rebuildingWebUI = ref(false)
const buildDialogVisible = ref(false)
const restartConfirmVisible = ref(false)
const buildLogs = ref('')
const buildDialogStatus = ref('')
const buildLogCardRef = ref<HTMLElement | null>(null)
const { t } = useI18n()
const noticeStore = useNoticeStore()
const { restarting, restartAndReload } = useRestartController()
let refreshTimer: number | null = null

const statusBadgeVariant = computed<DashboardTone>(() =>
  status.value?.status === 'running' ? 'default' : 'secondary',
)

const primaryStats = computed<DashboardStat[]>(() => [
  {
    key: 'status',
    label: t('dashboard.status'),
    value: status.value?.status || '...',
    icon: status.value?.status === 'running' ? CheckCircle2 : AlertCircle,
    variant: statusBadgeVariant.value,
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
    variant: 'secondary' satisfies DashboardTone,
  },
])

const secondaryStats = computed<DashboardStat[]>(() => [
  {
    key: 'disabled-plugins',
    label: t('dashboard.disabledPlugins'),
    value: status.value?.disabled_plugins_count ?? '...',
    icon: Plug,
    variant: 'secondary' satisfies DashboardTone,
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
    variant: 'secondary' satisfies DashboardTone,
  },
  {
    key: 'access-rules',
    label: t('dashboard.accessRules'),
    value: status.value?.access_rules_count ?? '...',
    icon: ShieldCheck,
    variant: 'outline' satisfies DashboardTone,
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

const eventSummary = computed(() => {
  const important = recentEvents.value.find(event =>
    event.level === 'ERROR' || event.level === 'CRITICAL' || event.level === 'WARNING',
  )
  return important?.level || (recentEvents.value.length ? recentEvents.value[0].level : t('dashboard.noEvents'))
})

const hasRuntimeData = computed(() => Boolean(status.value))

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
  restartConfirmVisible.value = true
}

async function confirmRestart() {
  restartConfirmVisible.value = false
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

function eventBadgeVariant(level: string): DashboardTone {
  if (level === 'ERROR' || level === 'CRITICAL') {
    return 'destructive'
  }
  if (level === 'WARNING') {
    return 'secondary'
  }
  return 'outline'
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
  <div class="dashboard-workbench">
    <Alert v-if="dashboardError" variant="destructive">
      <AlertCircle />
      <AlertTitle>{{ t('dashboard.refreshFailed') }}</AlertTitle>
      <AlertDescription>{{ dashboardError }}</AlertDescription>
    </Alert>

    <section class="dashboard-command-bar">
      <div class="dashboard-command-bar__title">
        <Badge :variant="statusBadgeVariant">
          {{ status?.status || t('common.loading') }}
        </Badge>
        <div>
          <h1>{{ t('dashboard.title') }}</h1>
          <p>{{ t('dashboard.summary', {
            plugins: status?.plugins_count ?? '...',
            adapters: status?.adapters?.length ?? '...',
            groups: status?.groups_count ?? '...',
          }) }}</p>
        </div>
      </div>

      <div class="dashboard-command-bar__actions">
        <Button :disabled="restarting" variant="outline" @click="handleRestart">
          <RefreshCw data-icon="inline-start" />
          {{ t('dashboard.restart') }}
        </Button>
        <Button :disabled="loading" variant="secondary" @click="refreshDashboard()">
          <RefreshCw :class="{ 'animate-spin': loading }" data-icon="inline-start" />
          {{ t('common.refresh') }}
        </Button>
      </div>
    </section>

    <div class="dashboard-status-strip">
      <Card v-for="item in primaryStats" :key="item.key" class="dashboard-status-card">
        <CardContent>
          <component :is="item.icon" />
          <div>
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </CardContent>
      </Card>
      <Card class="dashboard-status-card">
        <CardContent>
          <History />
          <div>
            <span>{{ t('dashboard.recentEvents') }}</span>
            <strong>{{ eventSummary }}</strong>
          </div>
        </CardContent>
      </Card>
    </div>

    <section class="dashboard-ops-grid">
      <Card class="dashboard-runtime-card">
        <CardHeader>
          <div>
            <CardTitle>{{ t('dashboard.adapterList') }}</CardTitle>
            <CardDescription>{{ t('dashboard.noAdaptersText') }}</CardDescription>
          </div>
          <Badge variant="outline">
            {{ status?.adapters?.length ?? 0 }}
          </Badge>
        </CardHeader>
        <CardContent>
          <div v-if="loading && !hasRuntimeData" class="dashboard-skeleton-list">
            <Skeleton v-for="index in 4" :key="index" class="h-8" />
          </div>
          <div v-else-if="status?.adapters?.length" class="dashboard-adapter-list">
            <Badge
              v-for="adapter in status.adapters"
              :key="adapter"
              variant="secondary"
            >
              {{ adapter }}
            </Badge>
          </div>
          <Empty v-else class="dashboard-empty">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Cable />
              </EmptyMedia>
              <EmptyTitle>{{ t('dashboard.noAdapters') }}</EmptyTitle>
              <EmptyDescription>{{ t('dashboard.noAdaptersText') }}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        </CardContent>
      </Card>

      <Card class="dashboard-secondary-card">
        <CardHeader>
          <CardTitle>{{ t('dashboard.extraStats') }}</CardTitle>
          <CardDescription>{{ t('dashboard.description') }}</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableBody>
              <TableRow v-for="item in secondaryStats" :key="item.key">
                <TableCell>
                  <div class="dashboard-stat-label">
                    <component :is="item.icon" />
                    <span>{{ item.label }}</span>
                  </div>
                </TableCell>
                <TableCell class="dashboard-stat-value">
                  <Badge :variant="item.variant">
                    {{ item.value }}
                  </Badge>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card class="dashboard-events-card">
        <CardHeader>
          <div>
            <CardTitle>{{ t('dashboard.recentEvents') }}</CardTitle>
            <CardDescription>{{ t('dashboard.openLogs') }}</CardDescription>
          </div>
          <Button as-child size="sm" variant="ghost">
            <RouterLink to="/logs/live">
              {{ t('dashboard.openLogs') }}
            </RouterLink>
          </Button>
        </CardHeader>
        <CardContent>
          <div v-if="loading && recentEvents.length === 0" class="dashboard-skeleton-list">
            <Skeleton v-for="index in 3" :key="index" class="h-12" />
          </div>

          <Empty v-else-if="recentEvents.length === 0" class="dashboard-empty">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <History />
              </EmptyMedia>
              <EmptyTitle>{{ t('dashboard.noEvents') }}</EmptyTitle>
            </EmptyHeader>
          </Empty>

          <Table v-else>
            <TableHeader>
              <TableRow>
                <TableHead>{{ t('dashboard.status') }}</TableHead>
                <TableHead>{{ t('dashboard.eventSource') }}</TableHead>
                <TableHead>{{ t('logs.message') }}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="event in recentEvents"
                :key="`${event.timestamp}:${event.source}:${event.message}`"
              >
                <TableCell>
                  <Badge :variant="eventBadgeVariant(event.level)">
                    {{ event.level }}
                  </Badge>
                </TableCell>
                <TableCell class="dashboard-event-source">
                  {{ event.source }}
                  <span>{{ event.timestamp }}</span>
                </TableCell>
                <TableCell class="dashboard-event-message">
                  {{ event.message }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Alert v-if="showWebUIBuildCard" class="dashboard-build-alert">
        <TerminalSquare />
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

      <Alert v-else class="dashboard-build-alert dashboard-build-alert--quiet">
        <TerminalSquare />
        <AlertTitle>{{ t('dashboard.rebuildWebUI') }}</AlertTitle>
        <AlertDescription>
          {{ webuiBuildStatus ? t('dashboard.webuiBuildUpdated') : t('common.loading') }}
        </AlertDescription>
      </Alert>
    </section>

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

    <AlertDialog v-model:open="restartConfirmVisible">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{{ t('dashboard.restart') }}</AlertDialogTitle>
          <AlertDialogDescription>{{ t('dashboard.restartConfirm') }}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{{ t('common.cancel') }}</AlertDialogCancel>
          <AlertDialogAction :disabled="restarting" @click="confirmRestart">
            <RefreshCw data-icon="inline-start" />
            {{ t('common.confirm') }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
