<script setup lang="ts">
import type {
  GitCheckoutState,
  ProjectReleaseCandidate,
  ProjectUpdateChannel,
  ProjectUpdateMessage,
  ProjectUpdatePlan,
  ProjectUpdatePlanRequest,
  ProjectUpdateReleaseTrack,
  ProjectUpdateStatus,
  ProjectUpdateTask,
} from '@/api/projectUpdate'
import type { WorkbenchTone } from '@/components/management'
import {
  AlertTriangle,
  GitBranch,
  GitCommitHorizontal,
  History,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  UploadCloud,
} from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import {
  createProjectUpdateTask,
  getProjectUpdateStatus,
  getProjectUpdateTask,
  previewProjectUpdatePlan,
  refreshProjectUpdateStatus,
} from '@/api/projectUpdate'
import {
  ActionWithReason,
  LoadingSkeleton,
  PageScaffold,
  Panel,
  StatusBadge,
  TaskDialog,
} from '@/components/management'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  AlertDialog,
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
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useRestartController } from '@/composables/useRestartController'
import { useAuthStore } from '@/stores/auth'
import { useNoticeStore } from '@/stores/notice'
import { taskStatusTone } from '@/utils/feedbackState'
import {
  buildProjectUpdatePlanRequest,
  isProjectUpdateTaskActive,
  projectUpdateCandidatesForTrack,
  projectUpdateRestartRequired,
  resolveProjectUpdateActionState,
  selectProjectUpdateTarget,
} from '@/utils/projectUpdateState'

type CheckoutFact = {
  key: string
  label: string
  value: string
  mono?: boolean
}

const { t } = useI18n()
const authStore = useAuthStore()
const noticeStore = useNoticeStore()
const { restarting, restartAndReload } = useRestartController()

const status = ref<ProjectUpdateStatus | null>(null)
const plan = ref<ProjectUpdatePlan | null>(null)
const activeTask = ref<ProjectUpdateTask | null>(null)
const selectedChannel = ref<ProjectUpdateChannel>('release')
const releaseTrack = ref<ProjectUpdateReleaseTrack>('stable')
const selectedTag = ref('')
const loadingStatus = ref(false)
const refreshingRemote = ref(false)
const loadingPlan = ref(false)
const startingTask = ref(false)
const statusError = ref('')
const planError = ref('')
const rollbackConfirmVisible = ref(false)
const taskDialogVisible = ref(false)
let planSequence = 0
let taskPollTimer: number | null = null

const releaseCandidates = computed(() =>
  projectUpdateCandidatesForTrack(status.value, releaseTrack.value) as ProjectReleaseCandidate[],
)
const selectedCandidate = computed(() =>
  releaseCandidates.value.find(candidate => candidate.tag === selectedTag.value) || null,
)
const activeTaskRunning = computed(() =>
  isProjectUpdateTaskActive(activeTask.value?.status),
)
const planMessages = computed(() => [
  ...(plan.value?.blockers || []),
  ...(plan.value?.warnings || []),
])
const actionState = computed(() =>
  resolveProjectUpdateActionState({
    isAuthenticated: authStore.isAuthenticated,
    plan: plan.value,
    planLoading: loadingPlan.value,
    statusLoading: loadingStatus.value,
    taskActive: activeTaskRunning.value || startingTask.value,
  }),
)
const actionReason = computed(() => {
  if (actionState.value.reasonMessage) {
    return actionState.value.reasonMessage
  }
  if (!actionState.value.reasonCode) {
    return ''
  }
  return t(`update.actionReason.${actionState.value.reasonCode}`)
})
const checkoutFacts = computed<CheckoutFact[]>(() => {
  const checkout = status.value?.checkout
  if (!checkout) {
    return []
  }
  return [
    {
      key: 'branch',
      label: t('update.currentBranch'),
      value: checkout.branch || (checkout.is_detached ? t('update.detachedHead') : t('common.none')),
      mono: Boolean(checkout.branch),
    },
    {
      key: 'commit',
      label: t('update.currentCommit'),
      value: checkout.short_commit || shortCommit(checkout.current_commit),
      mono: true,
    },
    {
      key: 'upstream',
      label: t('update.branchUpstream'),
      value: checkout.upstream_ref || t('common.none'),
      mono: Boolean(checkout.upstream_ref),
    },
    {
      key: 'ahead-behind',
      label: t('update.aheadBehind'),
      value: t('update.aheadBehindValue', {
        ahead: checkout.ahead ?? 0,
        behind: checkout.behind ?? 0,
      }),
      mono: true,
    },
  ]
})
const branchTone = computed(() =>
  status.value?.branch.available ? 'success' : 'warning',
)
const releaseEmptyText = computed(() =>
  releaseTrack.value === 'stable'
    ? t('update.noStableReleases')
    : t('update.noPrereleases'),
)
const planTargetLabel = computed(() => {
  if (!plan.value) {
    return t('common.none')
  }
  return plan.value.target_tag
    || plan.value.target_ref
    || shortCommit(plan.value.target_commit)
    || t('common.none')
})
const taskStatusLabel = computed(() => {
  const statusValue = activeTask.value?.status || ''
  if (!statusValue) {
    return ''
  }
  const key = `taskDialog.status.${statusValue}`
  const translated = t(key)
  return translated === key ? statusValue : translated
})
const taskRestartReady = computed(() => projectUpdateRestartRequired(activeTask.value))
const selectedTargetSummary = computed(() => {
  if (selectedChannel.value === 'branch') {
    const branch = status.value?.branch
    return branch?.target_ref
      ? t('update.branchTargetSummary', {
        ref: branch.target_ref,
        commit: shortCommit(branch.target_commit),
      })
      : t('update.branchTargetUnavailable')
  }
  if (!selectedCandidate.value) {
    return releaseEmptyText.value
  }
  return candidateSummary(selectedCandidate.value)
})

watch(releaseCandidates, candidates => {
  selectedTag.value = selectProjectUpdateTarget(candidates, selectedTag.value)
}, { immediate: true })

watch([selectedChannel, releaseTrack, selectedTag], () => {
  void refreshPlan()
})

onMounted(() => {
  void refreshStatus()
})

onBeforeUnmount(() => {
  stopTaskPolling()
})

async function refreshStatus(options: { silent?: boolean } = {}) {
  loadingStatus.value = true
  try {
    const response = await getProjectUpdateStatus()
    status.value = response.data
    activeTask.value = response.data.active_task
    if (response.data.active_task) {
      taskDialogVisible.value = true
      if (isProjectUpdateTaskActive(response.data.active_task.status)) {
        startTaskPolling(response.data.active_task.task_id)
      }
    }
    statusError.value = ''
    await refreshPlan()
  } catch (error) {
    statusError.value = getErrorMessage(error, t('update.statusLoadFailed'))
    if (!options.silent) {
      noticeStore.show(statusError.value, 'error')
    }
  } finally {
    loadingStatus.value = false
  }
}

async function refreshRemoteStatus() {
  if (refreshingRemote.value) {
    return
  }
  refreshingRemote.value = true
  try {
    const response = await refreshProjectUpdateStatus()
    status.value = response.data
    activeTask.value = response.data.active_task
    statusError.value = ''
    await refreshPlan()
  } catch (error) {
    const message = getErrorMessage(error, t('update.remoteRefreshFailed'))
    statusError.value = message
    noticeStore.show(message, 'error')
  } finally {
    refreshingRemote.value = false
  }
}

async function refreshPlan() {
  const request = buildPlanRequest()
  if (!request) {
    plan.value = null
    planError.value = ''
    return
  }
  const sequence = ++planSequence
  loadingPlan.value = true
  try {
    const response = await previewProjectUpdatePlan(request)
    if (sequence === planSequence) {
      plan.value = response.data
      planError.value = ''
    }
  } catch (error) {
    if (sequence === planSequence) {
      plan.value = null
      planError.value = getErrorMessage(error, t('update.planLoadFailed'))
    }
  } finally {
    if (sequence === planSequence) {
      loadingPlan.value = false
    }
  }
}

function buildPlanRequest(): ProjectUpdatePlanRequest | null {
  if (selectedChannel.value === 'release' && releaseCandidates.value.length === 0) {
    return null
  }
  return buildProjectUpdatePlanRequest(
    selectedChannel.value,
    releaseTrack.value,
    selectedTag.value,
    selectedCandidate.value?.is_rollback ? 'rollback' : undefined,
  ) as ProjectUpdatePlanRequest
}

function requestApply() {
  if (actionState.value.disabled) {
    return
  }
  if (actionState.value.confirmationRequired) {
    rollbackConfirmVisible.value = true
    return
  }
  void startProjectUpdate()
}

async function confirmRollback() {
  rollbackConfirmVisible.value = false
  await startProjectUpdate('rollback')
}

async function startProjectUpdate(operation?: 'rollback') {
  const request = buildPlanRequest()
  if (!request || startingTask.value) {
    return
  }
  startingTask.value = true
  try {
    const response = await createProjectUpdateTask(
      operation ? { ...request, operation } : request,
    )
    activeTask.value = response.data
    taskDialogVisible.value = true
    startTaskPolling(response.data.task_id)
    noticeStore.show(t('update.updateStarted'), 'success')
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('update.updateFailed')), 'error')
  } finally {
    startingTask.value = false
  }
}

function startTaskPolling(taskId: string) {
  stopTaskPolling()
  taskPollTimer = window.setInterval(async () => {
    try {
      const response = await getProjectUpdateTask(taskId)
      activeTask.value = response.data
      if (!isProjectUpdateTaskActive(response.data.status)) {
        stopTaskPolling()
        if (response.data.status === 'succeeded') {
          noticeStore.show(t('update.updateSucceeded'), 'success')
          await refreshStatus({ silent: true })
        } else {
          noticeStore.show(response.data.error || t('update.updateFailed'), 'error')
        }
      }
    } catch (error) {
      stopTaskPolling()
      noticeStore.show(getErrorMessage(error, t('update.updateFailed')), 'error')
    }
  }, 1000)
}

function stopTaskPolling() {
  if (taskPollTimer !== null) {
    window.clearInterval(taskPollTimer)
    taskPollTimer = null
  }
}

async function restartAfterUpdate() {
  await restartAndReload()
}

function localizedMessage(message: ProjectUpdateMessage) {
  const key = `update.message.${message.code}`
  const translated = t(key)
  return translated === key ? message.message : translated
}

function messageDetail(message: ProjectUpdateMessage) {
  return message.detail || ''
}

function candidateSummary(candidate: ProjectReleaseCandidate) {
  const metadata = candidate.metadata
  const schema = metadata.database_schema_min !== null || metadata.database_schema_max !== null
    ? `${metadata.database_schema_min ?? '*'}-${metadata.database_schema_max ?? '*'}`
    : t('update.unknownCompatibility')
  return t('update.releaseCandidateSummary', {
    version: candidate.version,
    commit: shortCommit(candidate.commit),
    schema,
  })
}

function candidateTone(candidate: ProjectReleaseCandidate): WorkbenchTone {
  if (candidate.blockers.length) {
    return 'error'
  }
  if (candidate.is_rollback || candidate.warnings.length) {
    return 'warning'
  }
  if (candidate.is_current) {
    return 'info'
  }
  return 'success'
}

function shortCommit(value: string | null | undefined) {
  return value ? value.slice(0, 12) : t('common.none')
}

function dirtyEntries(checkout: GitCheckoutState | undefined) {
  return checkout?.dirty_entries.slice(0, 5) || []
}

function formatRemoteRefreshTime(value: string | null | undefined) {
  if (!value) {
    return t('update.neverChecked')
  }
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) {
    return value
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(timestamp))
}
</script>

<template>
  <PageScaffold
    :aria-busy="loadingStatus || loadingPlan"
    :error-message="statusError"
    :retry-label="t('feedback.retry')"
    dense
    :subtitle="t('update.description')"
    :title="t('update.title')"
    @retry="refreshStatus"
  >
    <template #actions>
      <Button
        :disabled="loadingStatus || refreshingRemote"
        size="sm"
        variant="outline"
        @click="refreshRemoteStatus"
      >
        <RefreshCw data-icon="inline-start" />
        {{ refreshingRemote ? t('update.refreshingRemote') : t('update.refreshRemote') }}
      </Button>
      <ActionWithReason
        :disabled="actionState.disabled"
        :icon="actionState.confirmationRequired ? RotateCcw : UploadCloud"
        :label="t(actionState.labelKey)"
        :reason="actionReason"
        size="sm"
        :variant="actionState.confirmationRequired ? 'destructive' : 'default'"
        @activate="requestApply"
      />
    </template>

    <template #alerts>
      <Alert v-if="planError" variant="destructive">
        <AlertTriangle />
        <AlertTitle>{{ t('update.planLoadFailed') }}</AlertTitle>
        <AlertDescription>{{ planError }}</AlertDescription>
      </Alert>

      <Alert v-if="taskRestartReady" class="project-update-restart-alert">
        <RefreshCw />
        <AlertTitle>{{ t('update.restartRequiredTitle') }}</AlertTitle>
        <AlertDescription>
          <div class="project-update-alert-body">
            <span>{{ t('update.restartRequiredDescription') }}</span>
            <Button :disabled="restarting" size="sm" @click="restartAfterUpdate">
              <RefreshCw data-icon="inline-start" />
              {{ t('update.restartNow') }}
            </Button>
          </div>
        </AlertDescription>
      </Alert>
    </template>

    <LoadingSkeleton
      v-if="loadingStatus && !status"
      :busy-label="t('common.loading')"
      rows="6"
    />

    <div v-else class="project-update-compact">
      <Panel
        :subtitle="t('update.checkoutDescription')"
        :title="t('update.checkoutTitle')"
      >
        <div v-if="status" class="project-update-facts">
          <div
            v-for="fact in checkoutFacts"
            :key="fact.key"
            class="project-update-fact"
          >
            <span>{{ fact.label }}</span>
            <strong :class="{ monospace: fact.mono }">{{ fact.value }}</strong>
          </div>
        </div>
        <div v-else class="project-update-skeleton-list">
          <Skeleton v-for="index in 4" :key="index" class="h-12 w-full" />
        </div>

        <div v-if="status" class="project-update-remote-state">
          <span>
            {{
              t('update.remoteLastChecked', {
                time: formatRemoteRefreshTime(status.remote_refresh.last_success_at),
              })
            }}
          </span>
          <Badge :variant="status.remote_refresh.stale ? 'outline' : 'secondary'">
            {{
              status.remote_refresh.stale
                ? t('update.remoteStatusStale')
                : t('update.remoteStatusFresh')
            }}
          </Badge>
        </div>

        <Alert
          v-if="status?.remote_refresh.last_error"
          class="project-update-message project-update-message--warning"
        >
          <AlertTriangle />
          <AlertTitle>{{ t('update.remoteRefreshFailed') }}</AlertTitle>
          <AlertDescription>{{ status.remote_refresh.last_error }}</AlertDescription>
        </Alert>

        <Alert
          v-if="status?.checkout.dirty"
          class="project-update-message project-update-message--warning"
        >
          <AlertTriangle />
          <AlertTitle>{{ t('update.dirtyWorktree') }}</AlertTitle>
          <AlertDescription>
            <div class="project-update-message-list">
              <span>{{ t('update.dirtyWorktreeDescription') }}</span>
              <code v-for="entry in dirtyEntries(status?.checkout)" :key="entry">
                {{ entry }}
              </code>
            </div>
          </AlertDescription>
        </Alert>

        <div v-if="status?.checkout.blockers.length" class="project-update-message-stack">
          <Alert
            v-for="message in status.checkout.blockers"
            :key="message.code"
            class="project-update-message project-update-message--warning"
          >
            <ShieldAlert />
            <AlertTitle>{{ localizedMessage(message) }}</AlertTitle>
            <AlertDescription v-if="messageDetail(message)">
              {{ messageDetail(message) }}
            </AlertDescription>
          </Alert>
        </div>
      </Panel>

      <Panel
        :subtitle="t('update.channelDescription')"
        :title="t('update.projectUpdate')"
      >
        <div class="project-update-control-stack">
          <div class="project-update-control-row">
            <div>
              <span>{{ t('update.channel') }}</span>
              <strong>{{ t(`update.channelValue.${selectedChannel}`) }}</strong>
            </div>
            <ToggleGroup
              v-model="selectedChannel"
              type="single"
              @update:model-value="value => value && (selectedChannel = String(value) as ProjectUpdateChannel)"
            >
              <ToggleGroupItem value="release">
                <History data-icon="inline-start" />
                {{ t('update.releaseChannel') }}
              </ToggleGroupItem>
              <ToggleGroupItem value="branch">
                <GitBranch data-icon="inline-start" />
                {{ t('update.branchChannel') }}
              </ToggleGroupItem>
            </ToggleGroup>
          </div>

          <section v-if="selectedChannel === 'branch'" class="project-update-channel-panel">
            <div class="project-update-target-box">
              <GitCommitHorizontal />
              <div>
                <span>{{ t('update.target') }}</span>
                <strong>{{ selectedTargetSummary }}</strong>
              </div>
              <StatusBadge
                :label="status?.branch.available ? t('update.available') : t('update.blocked')"
                :tone="branchTone"
              />
            </div>
          </section>

          <section v-else class="project-update-channel-panel">
            <div class="project-update-control-row project-update-control-row--top">
              <div>
                <span>{{ t('update.releaseTrack') }}</span>
                <strong>{{ t(`update.trackValue.${releaseTrack}`) }}</strong>
              </div>
              <ToggleGroup
                v-model="releaseTrack"
                type="single"
                @update:model-value="value => value && (releaseTrack = String(value) as ProjectUpdateReleaseTrack)"
              >
                <ToggleGroupItem value="stable">{{ t('update.stable') }}</ToggleGroupItem>
                <ToggleGroupItem value="prerelease">{{ t('update.prerelease') }}</ToggleGroupItem>
              </ToggleGroup>
            </div>

            <div class="project-update-select-row">
              <label for="project-update-release-target">{{ t('update.target') }}</label>
              <Select
                v-model="selectedTag"
                :disabled="releaseCandidates.length === 0"
              >
                <SelectTrigger id="project-update-release-target" class="project-update-select">
                  <SelectValue :placeholder="releaseEmptyText" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="candidate in releaseCandidates"
                      :key="candidate.tag"
                      :value="candidate.tag"
                    >
                      {{ candidate.tag }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div v-if="selectedCandidate" class="project-update-target-box">
              <GitCommitHorizontal />
              <div>
                <span>{{ selectedCandidate.tag }}</span>
                <strong>{{ candidateSummary(selectedCandidate) }}</strong>
              </div>
              <StatusBadge
                :label="
                  selectedCandidate.is_rollback
                    ? t('update.rollback')
                    : selectedCandidate.is_current
                      ? t('update.current')
                      : t('update.update')
                "
                :tone="candidateTone(selectedCandidate)"
              />
            </div>
            <Alert v-else class="project-update-message">
              <AlertTriangle />
              <AlertTitle>{{ releaseEmptyText }}</AlertTitle>
              <AlertDescription>{{ t('update.releaseEmptyDescription') }}</AlertDescription>
            </Alert>
          </section>

          <div v-if="loadingPlan" class="project-update-skeleton-list">
            <Skeleton v-for="index in 2" :key="index" class="h-10 w-full" />
          </div>

          <template v-else>
            <div class="project-update-plan-summary">
              <div>
                <span>{{ t('update.operation') }}</span>
                <strong>
                  {{
                    plan?.operation === 'rollback'
                      ? t('update.rollback')
                      : t('update.update')
                  }}
                </strong>
              </div>
              <div>
                <span>{{ t('update.confirmation') }}</span>
                <strong>
                  {{
                    plan?.confirmation === 'rollback'
                      ? t('update.rollbackRequired')
                      : t('update.updateConfirmation')
                  }}
                </strong>
              </div>
            </div>

            <div v-if="planMessages.length" class="project-update-message-stack">
              <Alert
                v-for="message in planMessages"
                :key="`${message.code}-${message.message}`"
                class="project-update-message"
                :class="plan?.blockers.includes(message)
                  ? 'project-update-message--error'
                  : 'project-update-message--warning'"
              >
                <ShieldAlert v-if="plan?.blockers.includes(message)" />
                <AlertTriangle v-else />
                <AlertTitle>{{ localizedMessage(message) }}</AlertTitle>
                <AlertDescription v-if="messageDetail(message)">
                  {{ messageDetail(message) }}
                </AlertDescription>
              </Alert>
            </div>

          </template>
        </div>
      </Panel>
    </div>

    <TaskDialog
      v-model="taskDialogVisible"
      :binding-value="activeTask?.target_version"
      :close-label="t('common.close')"
      :current-phase="activeTask?.current_phase"
      :current-phase-label="activeTask?.current_phase_label"
      :diagnostics="activeTask?.diagnostics || []"
      :loading="activeTaskRunning"
      :logs="activeTask?.logs || ''"
      :operation="activeTask?.operation"
      :raw-status="activeTask?.status"
      :requirement="activeTask?.target_tag || activeTask?.target_ref"
      resource-kind="project"
      :restart-required="activeTask?.restart_required"
      :status="taskStatusLabel"
      :status-tone="taskStatusTone(activeTask?.status)"
      :steps="activeTask?.steps || []"
      :title="activeTask?.title || t('update.taskTitle')"
      :waiting-text="t('update.taskWaiting')"
    />

    <AlertDialog v-model:open="rollbackConfirmVisible">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{{ t('update.rollbackTitle') }}</AlertDialogTitle>
          <AlertDialogDescription>
            {{ t('update.rollbackConfirm', { target: planTargetLabel }) }}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div class="project-update-rollback-summary">
          <Badge variant="outline">{{ releaseTrack }}</Badge>
          <strong>{{ planTargetLabel }}</strong>
          <span>{{ t('update.rollbackWarning') }}</span>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>{{ t('common.cancel') }}</AlertDialogCancel>
          <Button
            :disabled="startingTask"
            variant="destructive"
            @click="confirmRollback"
          >
            <RotateCcw data-icon="inline-start" />
            {{ t('update.applyRollback') }}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </PageScaffold>
</template>
