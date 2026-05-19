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

console.log('route-state helper tests passed')
