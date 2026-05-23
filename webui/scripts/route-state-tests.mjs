import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import ts from 'typescript'

const projectRoot = resolve(import.meta.dirname, '..')
const tempModules = new Map()

async function loadTsModule(relativePath) {
  const sourcePath = join(projectRoot, relativePath)
  const source = readFileSync(sourcePath, 'utf8')
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: sourcePath,
  }).outputText
  const encoded = Buffer.from(transpiled).toString('base64')
  const moduleUrl = `data:text/javascript;base64,${encoded}`
  if (!tempModules.has(moduleUrl)) {
    tempModules.set(moduleUrl, import(moduleUrl))
  }
  return tempModules.get(moduleUrl)
}

const {
  DEFAULT_AUTH_REDIRECT,
  buildAuthRedirect,
  normalizeAuthRedirect,
} = await loadTsModule('src/utils/routeRedirect.ts')
const {
  buildStoreRouteQuery,
  normalizeStoreRouteState,
  storeRouteStateEquals,
} = await loadTsModule('src/utils/storeRouteState.ts')
const {
  buildLiveLogRouteQuery,
  liveLogRouteStateEquals,
  normalizeLiveLogRouteState,
} = await loadTsModule('src/utils/liveLogRouteState.ts')
const {
  hasActiveFeedbackFilters,
  isTaskActive,
  isTaskTerminal,
  resolveCollectionFeedback,
  taskStatusTone,
} = await loadTsModule('src/utils/feedbackState.ts')
const {
  buildAIWorkbenchAreaQuery,
  normalizeAIWorkbenchArea,
  normalizeAIWorkbenchRouteState,
} = await loadTsModule('src/utils/aiRouteState.ts')
const {
  buildRouteSnapshot,
} = await loadTsModule('src/composables/aiModels/formState.ts')
const {
  buildProjectUpdatePlanRequest,
  isProjectUpdateTaskActive,
  hasProjectUpdateReleaseUpdate,
  projectUpdateCandidatesForTrack,
  projectUpdateRestartRequired,
  resolveProjectUpdateActionState,
  selectProjectUpdateTarget,
  shouldRefreshProjectUpdateRemote,
} = await loadTsModule('src/utils/projectUpdateState.ts')
const {
  filterPendingEntriesForRuntime,
  runtimeStartedAtFromUptime,
} = await loadTsModule('src/utils/restartPendingState.ts')

assert.equal(
  normalizeAuthRedirect('/plugins?filter=attention', 'http://localhost'),
  '/plugins?filter=attention',
)
assert.equal(normalizeAuthRedirect('https://evil.test/x', 'http://localhost'), DEFAULT_AUTH_REDIRECT)
assert.equal(normalizeAuthRedirect('//evil.test/x', 'http://localhost'), DEFAULT_AUTH_REDIRECT)
assert.equal(normalizeAuthRedirect('', 'http://localhost'), DEFAULT_AUTH_REDIRECT)
assert.equal(buildAuthRedirect('/store/plugins?page=2'), '/store/plugins?page=2')

const storeState = normalizeStoreRouteState({
  category: ' utility ',
  installed: 'hidden',
  page: '2',
  search: ' status ',
  sort: 'name',
  source: 'official',
})
assert.deepEqual(storeState, {
  category: 'utility',
  installedOnly: true,
  page: 2,
  search: 'status',
  sort: 'name',
  source: 'official',
})
assert.deepEqual(buildStoreRouteQuery(storeState), {
  category: 'utility',
  installed: 'hidden',
  page: '2',
  search: 'status',
  sort: 'name',
  source: 'official',
})
assert.equal(normalizeStoreRouteState({ installed: 'all' }).installedOnly, false)
assert.equal(normalizeStoreRouteState({ page: '-1', sort: 'unknown' }).page, 1)
assert.equal(normalizeStoreRouteState({ page: '-1', sort: 'unknown' }).sort, 'default')
assert.equal(
  storeRouteStateEquals(storeState, normalizeStoreRouteState(buildStoreRouteQuery(storeState))),
  true,
)

const liveState = normalizeLiveLogRouteState({
  advanced: '1',
  level: 'ERROR,WARNING,ERROR',
  raw: 'true',
  search: ' error ',
  source: ['apeiria', ' uvicorn.access '],
})
assert.deepEqual(liveState, {
  advanced: true,
  levels: ['ERROR', 'WARNING'],
  search: 'error',
  showAccessLogs: false,
  showRawRecords: true,
  sources: ['apeiria', 'uvicorn.access'],
})
assert.deepEqual(buildLiveLogRouteQuery({ ...liveState, showAccessLogs: true }), {
  advanced: '1',
  access: '1',
  level: 'ERROR,WARNING',
  raw: '1',
  search: 'error',
  source: 'apeiria,uvicorn.access',
})
assert.equal(
  liveLogRouteStateEquals(
    { ...liveState, showAccessLogs: true },
    normalizeLiveLogRouteState(buildLiveLogRouteQuery({ ...liveState, showAccessLogs: true })),
  ),
  true,
)

assert.deepEqual(resolveCollectionFeedback({
  loading: true,
  totalCount: 0,
  visibleCount: 0,
}), {
  ariaBusy: true,
  canRetry: false,
  emptyCause: '',
  hasError: false,
  isInitialLoading: true,
  isRefreshing: false,
  showEmpty: false,
  showStaleError: false,
})
assert.deepEqual(resolveCollectionFeedback({
  errorMessage: 'network failed',
  loading: true,
  totalCount: 3,
  visibleCount: 3,
}), {
  ariaBusy: true,
  canRetry: true,
  emptyCause: '',
  hasError: true,
  isInitialLoading: false,
  isRefreshing: true,
  showEmpty: false,
  showStaleError: true,
})
assert.deepEqual(resolveCollectionFeedback({
  hasFilters: true,
  loading: false,
  totalCount: 10,
  visibleCount: 0,
}).emptyCause, 'filtered')
assert.deepEqual(resolveCollectionFeedback({
  hasFilters: false,
  loading: false,
  totalCount: 0,
  visibleCount: 0,
}).emptyCause, 'no-data')
assert.equal(hasActiveFeedbackFilters(['', [], false, ' value ']), true)
assert.equal(hasActiveFeedbackFilters(['', [], false, null]), false)
assert.equal(isTaskActive('running'), true)
assert.equal(isTaskTerminal('failed'), true)
assert.equal(taskStatusTone('succeeded'), 'success')
assert.equal(taskStatusTone('failed'), 'error')
assert.equal(taskStatusTone('queued'), 'info')
assert.equal(taskStatusTone('idle'), 'default')
assert.equal(normalizeAIWorkbenchArea('skills'), 'skills')
assert.equal(normalizeAIWorkbenchArea('unknown'), 'models')
assert.deepEqual(normalizeAIWorkbenchRouteState({
  area: 'sessions',
  capability: 'embedding',
  debug: 'tools',
  model: 'model-1',
  profile: 'profile-1',
  session: 'session-1',
  source: 'source-1',
  trace: 'trace-1',
}), {
  area: 'sessions',
  localMode: {
    capability: 'embedding',
    debug: 'tools',
  },
  selectedIds: {
    model: 'model-1',
    profile: 'profile-1',
    session: 'session-1',
    source: 'source-1',
    trace: 'trace-1',
  },
})
assert.deepEqual(buildAIWorkbenchAreaQuery('knowledge', {
  area: 'models',
  capability: 'chat',
  context: 'profiles',
  extra: 'ignored',
  model: 'model-1',
  source: '',
}), {
  area: 'knowledge',
  capability: 'chat',
  model: 'model-1',
})

const updateStatus = {
  stable_releases: [
    { tag: 'v1.1.0', prerelease: false, is_current: false, is_rollback: false },
    { tag: 'v1.0.0', prerelease: false, is_current: true, is_rollback: false },
    { tag: 'v1.2.0-rc.1', prerelease: true },
  ],
  prerelease_releases: [
    { tag: 'v1.2.0-rc.1', prerelease: true },
    { tag: 'v1.0.0', prerelease: false },
  ],
}
assert.deepEqual(
  projectUpdateCandidatesForTrack(updateStatus, 'stable').map(item => item.tag),
  ['v1.1.0', 'v1.0.0'],
)
assert.deepEqual(
  projectUpdateCandidatesForTrack(updateStatus, 'prerelease').map(item => item.tag),
  ['v1.2.0-rc.1'],
)
assert.equal(
  selectProjectUpdateTarget(updateStatus.stable_releases, 'v1.0.0'),
  'v1.0.0',
)
assert.equal(
  selectProjectUpdateTarget(updateStatus.stable_releases, 'missing'),
  'v1.1.0',
)
assert.equal(hasProjectUpdateReleaseUpdate(updateStatus), true)
assert.equal(
  hasProjectUpdateReleaseUpdate({
    stable_releases: [{ tag: 'v1.0.0', prerelease: false, is_current: true }],
    prerelease_releases: [{ tag: 'v0.9.0-rc.1', prerelease: true, is_rollback: true }],
  }),
  false,
)
assert.equal(shouldRefreshProjectUpdateRemote(null), true)
assert.equal(shouldRefreshProjectUpdateRemote({ last_checked_at: null }), true)
assert.equal(
  shouldRefreshProjectUpdateRemote({
    stale: false,
    last_checked_at: '2026-05-20T00:00:00.000Z',
    next_check_after: '2026-05-20T00:30:00.000Z',
  }, new Date('2026-05-20T00:20:00.000Z')),
  false,
)
assert.equal(
  shouldRefreshProjectUpdateRemote({
    stale: false,
    last_checked_at: '2026-05-20T00:00:00.000Z',
    next_check_after: '2026-05-20T00:30:00.000Z',
  }, new Date('2026-05-20T00:30:01.000Z')),
  true,
)
assert.equal(
  shouldRefreshProjectUpdateRemote({
    stale: true,
    last_checked_at: '2026-05-20T00:00:00.000Z',
    next_check_after: '2026-05-20T00:05:00.000Z',
  }, new Date('2026-05-20T00:04:00.000Z')),
  false,
)
assert.deepEqual(
  buildProjectUpdatePlanRequest('branch', 'prerelease', 'v1.2.0-rc.1'),
  { channel: 'branch' },
)
assert.deepEqual(
  buildProjectUpdatePlanRequest('release', 'prerelease', 'v1.2.0-rc.1', 'rollback'),
  {
    channel: 'release',
    release_track: 'prerelease',
    target_tag: 'v1.2.0-rc.1',
    operation: 'rollback',
  },
)
assert.deepEqual(
  resolveProjectUpdateActionState({
    isOwner: true,
    plan: {
      allowed: false,
      operation: 'update',
      blockers: [{ message: 'dirty worktree' }],
    },
  }),
  {
    confirmationRequired: false,
    disabled: true,
    labelKey: 'update.applyUpdate',
    operation: 'update',
    reasonCode: 'blocked',
    reasonMessage: 'dirty worktree',
  },
)
assert.deepEqual(
  resolveProjectUpdateActionState({
    isOwner: true,
    plan: {
      allowed: true,
      operation: 'rollback',
      confirmation: 'rollback',
      blockers: [],
    },
  }),
  {
    confirmationRequired: true,
    disabled: false,
    labelKey: 'update.applyRollback',
    operation: 'rollback',
    reasonCode: '',
    reasonMessage: '',
  },
)
assert.equal(isProjectUpdateTaskActive('queued'), true)
assert.equal(isProjectUpdateTaskActive('succeeded'), false)
assert.equal(projectUpdateRestartRequired({ status: 'succeeded', restart_required: true }), true)
assert.equal(projectUpdateRestartRequired({ status: 'failed', restart_required: true }), false)

const runtimeStartedAt = runtimeStartedAtFromUptime(
  120,
  new Date('2026-05-23T10:00:00.000Z'),
)
assert.equal(runtimeStartedAt?.toISOString(), '2026-05-23T09:58:00.000Z')
assert.equal(runtimeStartedAtFromUptime(-1), null)
assert.equal(runtimeStartedAtFromUptime(Number.NaN), null)
assert.deepEqual(
  filterPendingEntriesForRuntime([
    { id: 'before-restart', updated_at: '2026-05-23T09:57:59.000Z' },
    { id: 'after-restart', updated_at: '2026-05-23T09:58:01.000Z' },
    { id: 'invalid-date', updated_at: 'not-a-date' },
  ], runtimeStartedAt).map(item => item.id),
  ['after-restart', 'invalid-date'],
)
assert.deepEqual(
  filterPendingEntriesForRuntime([
    { id: 'kept', updated_at: '2026-05-23T09:57:59.000Z' },
  ], null).map(item => item.id),
  ['kept'],
)

const routeSnapshot = buildRouteSnapshot({
  algorithm: 'ordered',
  enabled: true,
  fallback_on_failure: true,
  members: [
    {
      enabled: true,
      position: 0,
      profile_id: 'profile-primary',
      route_member_id: 'member-primary',
      weight: 1,
    },
    {
      deleted: true,
      enabled: false,
      position: 1,
      profile_id: 'profile-fallback',
      route_member_id: 'member-fallback',
      weight: 2,
    },
  ],
  mode: 'primary_fallback',
  name: ' Reply route ',
  route_id: 'route-1',
  task_class: 'reply_default',
})
assert.equal(routeSnapshot.includes('"name":"Reply route"'), true)
assert.equal(routeSnapshot.includes('"deleted":true'), true)
assert.equal(routeSnapshot.includes('"weight":2'), true)

console.log('route-state and feedback-state helper tests passed')
