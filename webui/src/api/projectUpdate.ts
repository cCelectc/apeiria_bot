import client from './client'

export type ProjectUpdateChannel = 'branch' | 'release'
export type ProjectUpdateOperation = 'update' | 'rollback'
export type ProjectUpdateReleaseTrack = 'stable' | 'prerelease'
export type ProjectUpdateTaskStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export interface ProjectUpdateMessage {
  code: string
  message: string
  detail: string | null
}

export interface ProjectReleaseMetadata {
  version: string | null
  database_schema_min: number | null
  database_schema_max: number | null
  requires_python: string | null
  source: string | null
  available: boolean
}

export interface ProjectReleaseCandidate {
  tag: string
  version: string
  commit: string
  prerelease: boolean
  metadata: ProjectReleaseMetadata
  is_current: boolean
  is_rollback: boolean
  blockers: ProjectUpdateMessage[]
  warnings: ProjectUpdateMessage[]
}

export interface GitCheckoutState {
  project_root: string
  is_git: boolean
  is_detached: boolean
  branch: string | null
  current_commit: string | null
  short_commit: string | null
  upstream_ref: string | null
  upstream_commit: string | null
  ahead: number | null
  behind: number | null
  dirty: boolean
  dirty_entries: string[]
  head_tags: string[]
  blockers: ProjectUpdateMessage[]
}

export interface BranchUpdateState {
  available: boolean
  target_ref: string | null
  target_commit: string | null
  blockers: ProjectUpdateMessage[]
  warnings: ProjectUpdateMessage[]
}

export interface ProjectUpdateRemoteRefreshState {
  ttl_seconds: number
  stale: boolean
  last_checked_at: string | null
  last_success_at: string | null
  next_check_after: string | null
  last_error_at: string | null
  last_error: string | null
  remotes: string[]
}

export interface ProjectUpdateTaskStep {
  phase: string
  label: string
  status: string
  detail: string | null
  command: string | null
  output_excerpt: string | null
  started_at: string | null
  finished_at: string | null
}

export interface ProjectUpdateTask {
  task_id: string
  title: string
  status: ProjectUpdateTaskStatus
  logs: string
  error: string | null
  result: Record<string, unknown>
  created_at: string | null
  started_at: string | null
  finished_at: string | null
  channel: ProjectUpdateChannel | null
  operation: ProjectUpdateOperation | null
  target_ref: string | null
  target_commit: string | null
  target_tag: string | null
  target_version: string | null
  current_phase: string | null
  current_phase_label: string | null
  progress_percent: number | null
  restart_required: boolean
  steps: ProjectUpdateTaskStep[]
  diagnostics: Array<Record<string, unknown>>
}

export interface ProjectUpdateStatus {
  project_root: string
  checkout: GitCheckoutState
  branch: BranchUpdateState
  remote_refresh: ProjectUpdateRemoteRefreshState
  stable_releases: ProjectReleaseCandidate[]
  prerelease_releases: ProjectReleaseCandidate[]
  active_task: ProjectUpdateTask | null
}

export interface ProjectUpdatePlanRequest {
  channel: ProjectUpdateChannel
  release_track?: ProjectUpdateReleaseTrack
  target_tag?: string
  operation?: ProjectUpdateOperation
}

export interface ProjectUpdatePlan {
  channel: ProjectUpdateChannel
  operation: ProjectUpdateOperation
  target_ref: string | null
  target_commit: string | null
  release_track: ProjectUpdateReleaseTrack | null
  target_tag: string | null
  target_version: string | null
  allowed: boolean
  blockers: ProjectUpdateMessage[]
  warnings: ProjectUpdateMessage[]
  steps: string[]
  confirmation: 'update' | 'rollback' | string
}

export function getProjectUpdateStatus() {
  return client.get<ProjectUpdateStatus>('/update/status')
}

export function refreshProjectUpdateStatus() {
  return client.post<ProjectUpdateStatus>('/update/refresh')
}

export function previewProjectUpdatePlan(payload: ProjectUpdatePlanRequest) {
  return client.post<ProjectUpdatePlan>('/update/plan', payload)
}

export function createProjectUpdateTask(payload: ProjectUpdatePlanRequest) {
  return client.post<ProjectUpdateTask>('/update/tasks', payload)
}

export function getProjectUpdateTask(taskId: string) {
  return client.get<ProjectUpdateTask>(`/update/tasks/${encodeURIComponent(taskId)}`)
}
