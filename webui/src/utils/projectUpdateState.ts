export type ProjectUpdateChannelValue = 'branch' | 'release'
export type ProjectUpdateReleaseTrackValue = 'stable' | 'prerelease'
export type ProjectUpdateOperationValue = 'update' | 'rollback'

export interface ProjectUpdateCandidateLike {
  tag: string
  prerelease: boolean
  is_current?: boolean
  is_rollback?: boolean
}

export interface ProjectUpdateStatusLike {
  stable_releases?: readonly ProjectUpdateCandidateLike[]
  prerelease_releases?: readonly ProjectUpdateCandidateLike[]
}

export interface ProjectUpdateRemoteRefreshLike {
  stale?: boolean
  next_check_after?: string | null
  last_checked_at?: string | null
}

export interface ProjectUpdateMessageLike {
  message?: string | null
}

export interface ProjectUpdatePlanLike {
  allowed?: boolean
  operation?: ProjectUpdateOperationValue | string | null
  confirmation?: string | null
  blockers?: readonly ProjectUpdateMessageLike[]
}

export interface ProjectUpdatePlanRequestLike {
  channel: ProjectUpdateChannelValue
  release_track?: ProjectUpdateReleaseTrackValue
  target_tag?: string
  operation?: ProjectUpdateOperationValue
}

export type ProjectUpdateActionReasonCode =
  | ''
  | 'owner_required'
  | 'status_loading'
  | 'plan_loading'
  | 'plan_unavailable'
  | 'task_running'
  | 'blocked'

export interface ProjectUpdateActionState {
  disabled: boolean
  labelKey: 'update.applyUpdate' | 'update.applyRollback'
  reasonCode: ProjectUpdateActionReasonCode
  reasonMessage: string
  confirmationRequired: boolean
  operation: ProjectUpdateOperationValue
}

export interface ProjectUpdateActionInput {
  isOwner: boolean
  plan: ProjectUpdatePlanLike | null
  planLoading?: boolean
  statusLoading?: boolean
  taskActive?: boolean
}

const ACTIVE_TASK_STATUSES = new Set(['pending', 'queued', 'running'])

export function projectUpdateCandidatesForTrack(
  status: ProjectUpdateStatusLike | null | undefined,
  track: ProjectUpdateReleaseTrackValue,
): ProjectUpdateCandidateLike[] {
  const candidates = track === 'stable'
    ? status?.stable_releases || []
    : status?.prerelease_releases || []
  return candidates.filter(candidate =>
    track === 'stable' ? !candidate.prerelease : candidate.prerelease,
  )
}

export function selectProjectUpdateTarget(
  candidates: readonly ProjectUpdateCandidateLike[],
  currentTag: string,
): string {
  if (currentTag && candidates.some(candidate => candidate.tag === currentTag)) {
    return currentTag
  }
  const updateCandidate = candidates.find(candidate =>
    !candidate.is_current && !candidate.is_rollback,
  )
  return updateCandidate?.tag || candidates[0]?.tag || ''
}

export function hasProjectUpdateReleaseUpdate(
  status: ProjectUpdateStatusLike | null | undefined,
): boolean {
  return [
    ...(status?.stable_releases || []),
    ...(status?.prerelease_releases || []),
  ].some(candidate => !candidate.is_current && !candidate.is_rollback)
}

export function shouldRefreshProjectUpdateRemote(
  remoteRefresh: ProjectUpdateRemoteRefreshLike | null | undefined,
  now: Date = new Date(),
): boolean {
  if (!remoteRefresh?.last_checked_at) {
    return true
  }
  if (remoteRefresh.stale) {
    if (!remoteRefresh.next_check_after) {
      return true
    }
    const nextCheck = Date.parse(remoteRefresh.next_check_after)
    return !Number.isFinite(nextCheck) || nextCheck <= now.getTime()
  }
  if (!remoteRefresh.next_check_after) {
    return false
  }
  const nextCheck = Date.parse(remoteRefresh.next_check_after)
  return Number.isFinite(nextCheck) && nextCheck <= now.getTime()
}

export function buildProjectUpdatePlanRequest(
  channel: ProjectUpdateChannelValue,
  releaseTrack: ProjectUpdateReleaseTrackValue,
  targetTag: string,
  operation?: ProjectUpdateOperationValue,
): ProjectUpdatePlanRequestLike {
  if (channel === 'branch') {
    return operation ? { channel, operation } : { channel }
  }
  return {
    channel,
    release_track: releaseTrack,
    ...(targetTag ? { target_tag: targetTag } : {}),
    ...(operation ? { operation } : {}),
  }
}

export function isProjectUpdateTaskActive(status: string | null | undefined): boolean {
  return ACTIVE_TASK_STATUSES.has(status || '')
}

export function projectUpdateRestartRequired(
  task: { status?: string | null, restart_required?: boolean } | null | undefined,
) {
  return task?.status === 'succeeded' && task.restart_required === true
}

export function resolveProjectUpdateActionState(
  input: ProjectUpdateActionInput,
): ProjectUpdateActionState {
  const operation = input.plan?.operation === 'rollback' ? 'rollback' : 'update'
  const confirmationRequired = input.plan?.confirmation === 'rollback' || operation === 'rollback'
  const base = {
    labelKey: confirmationRequired
      ? 'update.applyRollback'
      : 'update.applyUpdate',
    confirmationRequired,
    operation,
  } satisfies Pick<ProjectUpdateActionState, 'confirmationRequired' | 'labelKey' | 'operation'>

  if (!input.isOwner) {
    return disabledAction(base, 'owner_required')
  }
  if (input.statusLoading) {
    return disabledAction(base, 'status_loading')
  }
  if (input.planLoading) {
    return disabledAction(base, 'plan_loading')
  }
  if (input.taskActive) {
    return disabledAction(base, 'task_running')
  }
  if (!input.plan) {
    return disabledAction(base, 'plan_unavailable')
  }
  if (!input.plan.allowed) {
    return disabledAction(
      base,
      'blocked',
      firstMessage(input.plan.blockers) || '',
    )
  }
  return {
    ...base,
    disabled: false,
    reasonCode: '',
    reasonMessage: '',
  }
}

function disabledAction(
  base: Pick<ProjectUpdateActionState, 'confirmationRequired' | 'labelKey' | 'operation'>,
  reasonCode: ProjectUpdateActionReasonCode,
  reasonMessage = '',
): ProjectUpdateActionState {
  return {
    ...base,
    disabled: true,
    reasonCode,
    reasonMessage,
  }
}

function firstMessage(messages: readonly ProjectUpdateMessageLike[] | undefined) {
  return messages?.find(item => item.message?.trim())?.message?.trim() || ''
}
