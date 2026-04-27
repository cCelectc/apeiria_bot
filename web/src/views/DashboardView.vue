<template>
  <div class="dashboard-view page-view">
    <section class="dashboard-hero">
      <div class="dashboard-hero__top">
        <div class="dashboard-hero__intro">
          <span class="text-overline dashboard-kicker">{{ t('layout.brand') }}</span>
          <h1 class="page-title">{{ t('dashboard.title') }}</h1>
        </div>
        <div class="page-actions">
          <v-btn color="warning" :loading="restarting" variant="tonal" @click="handleRestart">
            {{ t('dashboard.restart') }}
          </v-btn>
          <v-btn :loading="loading" variant="tonal" @click="refreshDashboard">
            {{ t('common.refresh') }}
          </v-btn>
        </div>
      </div>
    </section>

    <section v-if="showWebUIBuildCard" class="dashboard-section">
      <v-card class="dashboard-build-card">
        <v-card-text class="dashboard-build-card__content">
          <div class="dashboard-build-card__text">
            <div class="text-subtitle-1 font-weight-medium">{{ webuiBuildHeadline }}</div>
            <div class="text-body-2 text-medium-emphasis">{{ webuiBuildDescription }}</div>
          </div>
          <v-btn
            color="warning"
            :disabled="!webuiBuildStatus?.can_build"
            :loading="rebuildingWebUI"
            variant="tonal"
            @click="handleRebuildWebUI"
          >
            {{ t('dashboard.rebuildWebUI') }}
          </v-btn>
        </v-card-text>
      </v-card>
    </section>

    <v-dialog v-model="buildDialogVisible" max-width="920">
      <v-card>
        <v-card-title>{{ t('dashboard.rebuildWebUI') }}</v-card-title>
        <v-card-text class="d-flex flex-column ga-4">
          <div class="text-body-2 text-medium-emphasis">
            {{ buildDialogStatus }}
          </div>
          <v-progress-linear
            v-if="rebuildingWebUI"
            color="warning"
            indeterminate
          />
          <div ref="buildLogCardRef" class="build-log-card">
            <pre class="build-log-card__content">{{ buildLogs || t('dashboard.webuiBuildWaiting') }}</pre>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn :disabled="rebuildingWebUI" variant="text" @click="buildDialogVisible = false">
            {{ t('common.close') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <section class="dashboard-section">
      <div class="dashboard-section__header">
        <div class="dashboard-section__title">{{ t('dashboard.overview') }}</div>
      </div>
      <v-alert
        v-if="dashboardError"
        class="mb-4"
        density="comfortable"
        type="warning"
        variant="tonal"
      >
        {{ dashboardError }}
      </v-alert>
      <v-row class="dashboard-overview">
        <v-col cols="12" md="3" sm="6">
          <v-card class="metric-card metric-card--status">
            <v-card-text class="metric-card__body">
              <div class="metric-card__topline">
                <div class="metric-card__label">{{ t('dashboard.status') }}</div>
                <div class="metric-card__icon" :class="`metric-card__icon--${statusColor}`">
                  <v-icon size="28">{{ statusIcon }}</v-icon>
                </div>
              </div>
              <div class="metric-card__value metric-card__value--status">{{ status?.status || '...' }}</div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="3" sm="6">
          <v-card class="metric-card">
            <v-card-text class="metric-card__body">
              <div class="metric-card__topline">
                <div class="metric-card__label">{{ t('dashboard.uptime') }}</div>
                <div class="metric-card__icon metric-card__icon--primary">
                  <v-icon size="28">mdi-clock-outline</v-icon>
                </div>
              </div>
              <div class="metric-card__value">{{ formatUptime(status?.uptime) }}</div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="3" sm="6">
          <v-card class="metric-card">
            <v-card-text class="metric-card__body">
              <div class="metric-card__topline">
                <div class="metric-card__label">{{ t('dashboard.plugins') }}</div>
                <div class="metric-card__icon metric-card__icon--accent">
                  <v-icon size="28">mdi-puzzle</v-icon>
                </div>
              </div>
              <div class="metric-card__value metric-card__value--number">{{ status?.plugins_count ?? '...' }}</div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="3" sm="6">
          <v-card class="metric-card">
            <v-card-text class="metric-card__body">
              <div class="metric-card__topline">
                <div class="metric-card__label">{{ t('dashboard.adapters') }}</div>
                <div class="metric-card__icon metric-card__icon--info">
                  <v-icon size="28">mdi-connection</v-icon>
                </div>
              </div>
              <div class="metric-card__value metric-card__value--number">{{ status?.adapters?.length ?? '...' }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </section>

    <section class="dashboard-grid">
      <v-card v-if="status?.adapters?.length" class="surface-card dashboard-grid__main">
        <v-card-text class="d-flex flex-column ga-3">
          <div class="surface-card__title">{{ t('dashboard.adapterList') }}</div>
          <div class="dashboard-adapter-list">
            <v-chip
              v-for="adapter in status.adapters"
              :key="adapter"
              color="info"
              size="small"
              variant="tonal"
            >
              {{ adapter }}
            </v-chip>
          </div>
        </v-card-text>
      </v-card>

      <div class="dashboard-grid__side">
        <div class="dashboard-section__header dashboard-section__header--tight">
          <div class="dashboard-section__title">{{ t('dashboard.extraStats') }}</div>
        </div>
        <v-row>
          <v-col cols="12" md="6" sm="6">
            <v-card class="compact-metric-card">
              <v-card-text class="compact-metric-card__body">
                <div class="compact-metric-card__label">{{ t('dashboard.disabledPlugins') }}</div>
                <div class="compact-metric-card__value">{{ status?.disabled_plugins_count ?? '...' }}</div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="6" sm="6">
            <v-card class="compact-metric-card">
              <v-card-text class="compact-metric-card__body">
                <div class="compact-metric-card__label">{{ t('dashboard.groups') }}</div>
                <div class="compact-metric-card__value">{{ status?.groups_count ?? '...' }}</div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="6" sm="6">
            <v-card class="compact-metric-card">
              <v-card-text class="compact-metric-card__body">
                <div class="compact-metric-card__label">{{ t('dashboard.disabledGroups') }}</div>
                <div class="compact-metric-card__value">{{ status?.disabled_groups_count ?? '...' }}</div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="6" sm="6">
            <v-card class="compact-metric-card">
              <v-card-text class="compact-metric-card__body">
                <div class="compact-metric-card__label">{{ t('dashboard.accessRules') }}</div>
                <div class="compact-metric-card__value">{{ status?.access_rules_count ?? '...' }}</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </div>
    </section>

    <section class="dashboard-section">
      <div class="dashboard-section__header">
        <div class="dashboard-section__title">{{ t('dashboard.recentEvents') }}</div>
      </div>
      <v-card class="page-panel dashboard-events-card">
        <div v-if="recentEvents.length === 0" class="pa-6 text-body-2 text-medium-emphasis text-center">
          {{ t('dashboard.noEvents') }}
        </div>
        <div v-else class="dashboard-events-list">
          <article
            v-for="event in recentEvents"
            :key="`${event.timestamp}:${event.source}:${event.message}`"
            class="dashboard-event"
          >
            <div class="dashboard-event__badge">
              <v-chip
                class="dashboard-event__chip"
                :color="eventColor(event.level)"
                size="small"
                variant="tonal"
              >
                {{ event.level }}
              </v-chip>
            </div>
            <div class="dashboard-event__content">
              <div class="dashboard-event__title">{{ event.message }}</div>
              <div class="dashboard-event__meta">
                <span>{{ event.timestamp }}</span>
                <span>{{ t('dashboard.eventSource') }}: {{ event.source }}</span>
              </div>
            </div>
          </article>
        </div>
      </v-card>
    </section>
  </div>
</template>

<script setup lang="ts">
  import type { DashboardEventItem, DashboardStatus, WebUIBuildStatus } from '@/api/dashboard'
  import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { getErrorMessage } from '@/api/client'
  import { getDashboardEvents, getStatus, getWebUIBuildStatus, streamRebuildWebUI } from '@/api/dashboard'
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

  const statusColor = computed(() => status.value?.status === 'running' ? 'success' : 'warning')
  const statusIcon = computed(() => status.value?.status === 'running' ? 'mdi-check-circle' : 'mdi-alert-circle')
  const webuiBuildHeadline = computed(() => {
    if (!webuiBuildStatus.value) return ''
    if (!webuiBuildStatus.value.is_built) return t('dashboard.webuiBuildMissing')
    return t('dashboard.webuiBuildOutdated')
  })
  const webuiBuildDescription = computed(() => {
    if (!webuiBuildStatus.value) return ''
    if (!webuiBuildStatus.value.can_build) return t('dashboard.webuiBuildUnavailable')
    return t('dashboard.webuiBuildDetail', {
      tool: webuiBuildStatus.value.build_tool || 'pnpm',
    })
  })
  const showWebUIBuildCard = computed(() =>
    Boolean(webuiBuildStatus.value && (!webuiBuildStatus.value.is_built || webuiBuildStatus.value.is_stale)),
  )

  async function refreshDashboard (options: { silent?: boolean } = {}) {
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

  async function handleRebuildWebUI () {
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

  function appendBuildLogs (chunk: string) {
    buildLogs.value += chunk
    void nextTick(() => {
      const container = buildLogCardRef.value
      if (!container) return
      container.scrollTop = container.scrollHeight
    })
  }

  async function waitForWebUIBuildRefresh () {
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

  async function handleRestart () {
    if (!window.confirm(t('dashboard.restartConfirm'))) return
    await restartAndReload()
  }

  function sleep (ms: number) {
    return new Promise(resolve => window.setTimeout(resolve, ms))
  }

  function formatUptime (seconds?: number): string {
    if (!seconds) return '...'
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    return `${h}h ${m}m`
  }

  function eventColor (level: string) {
    if (level === 'ERROR' || level === 'CRITICAL') return 'error'
    if (level === 'WARNING') return 'warning'
    return 'info'
  }

  function startAutoRefresh () {
    stopAutoRefresh()
    refreshTimer = window.setInterval(() => {
      void refreshDashboard({ silent: true })
    }, 15_000)
  }

  function stopAutoRefresh () {
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

<style scoped>
.dashboard-view {
  padding-bottom: 8px;
}

.dashboard-hero__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.dashboard-hero__intro {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dashboard-hero {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border-radius: var(--shape-large);
  background: rgb(var(--v-theme-surface-container));
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 2px 8px rgba(15, 23, 42, 0.05);
}

.dashboard-kicker {
  color: rgba(var(--v-theme-on-surface), 0.64);
  letter-spacing: 0.08em !important;
}

.dashboard-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dashboard-build-card {
  background: rgb(var(--v-theme-surface-container));
}

.dashboard-build-card__content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.dashboard-build-card__text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.build-log-card {
  max-height: 48vh;
  overflow: auto;
  padding: 14px 16px;
  border-radius: var(--shape-medium);
  background: rgb(var(--v-theme-surface-container-low));
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-outline-variant), 0.28);
}

.build-log-card__content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-family-mono);
  font-size: 0.83rem;
  line-height: 1.45;
}

.dashboard-section__header {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.dashboard-section__header--tight {
  margin-bottom: 4px;
}

.dashboard-section__title {
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.3;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 1fr);
  gap: 16px;
  align-items: start;
}

.dashboard-grid__side {
  display: flex;
  flex-direction: column;
}

.surface-card {
  background: rgb(var(--v-theme-primary-container));
  color: rgb(var(--v-theme-on-primary-container));
}

.dashboard-grid__main {
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 8px 20px rgba(21, 101, 192, 0.08) !important;
}

.dashboard-adapter-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.dashboard-event__title {
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.45;
  white-space: normal;
}

.dashboard-event__meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 4px;
  font-size: 0.85rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
  white-space: normal;
}

.dashboard-events-card {
  background:
    linear-gradient(180deg, rgba(var(--v-theme-surface-container-high), 0.8), rgba(var(--v-theme-surface), 0.96));
}

.dashboard-events-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px;
}

.dashboard-event {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  padding: 16px 18px;
  border-radius: var(--shape-large);
  background: rgba(var(--v-theme-background), 0.38);
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-outline-variant), 0.32);
}

.dashboard-event__badge {
  display: flex;
  justify-content: center;
  padding-top: 2px;
}

.dashboard-event__chip {
  min-width: 88px;
  justify-content: center;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.dashboard-event__content {
  min-width: 0;
}

@media (max-width: 1100px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .dashboard-events-list {
    padding: 16px;
  }

  .dashboard-event {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .dashboard-event__badge {
    justify-content: flex-start;
  }
}
</style>
