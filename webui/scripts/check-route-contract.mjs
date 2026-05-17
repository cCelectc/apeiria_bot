import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const routerFile = resolve(scriptDir, '../src/router/index.ts')
const pluginsWorkbenchFile = resolve(scriptDir, '../src/pages/PluginsWorkbenchPage.vue')
const routerSource = readFileSync(routerFile, 'utf8')
const pluginsWorkbenchSource = readFileSync(pluginsWorkbenchFile, 'utf8')

const forbiddenRouteFragments = [
  "path: 'ai/overview'",
  "path: 'ai/models'",
  "path: 'ai/sessions'",
  "path: 'ai/knowledge'",
  "path: 'ai/personas'",
  "path: 'ai/memories'",
  "path: 'ai/relationships'",
  "path: 'ai/profiles'",
  "path: 'ai/future-tasks'",
  "path: 'ai/skills'",
  "path: 'ai/debug'",
  "redirect: '/ai/overview'",
  "path: 'plugins/config'",
  "path: 'plugins/store'",
  "redirect: '/plugins/config'",
]

const requiredRouteFragments = [
  "path: 'ai'",
  "name: 'ai'",
  "path: 'plugins'",
  "name: 'plugins'",
]

const requiredPluginsWorkbenchFragments = [
  "value: 'rules'",
  '<PluginLoadingRulesPage />',
]

const failures = [
  ...forbiddenRouteFragments
    .filter(fragment => routerSource.includes(fragment))
    .map(fragment => `forbidden route fragment still exists: ${fragment}`),
  ...requiredRouteFragments
    .filter(fragment => !routerSource.includes(fragment))
    .map(fragment => `required route fragment missing: ${fragment}`),
  ...requiredPluginsWorkbenchFragments
    .filter(fragment => !pluginsWorkbenchSource.includes(fragment))
    .map(fragment => `required plugin workbench fragment missing: ${fragment}`),
]

if (failures.length > 0) {
  console.error('Route contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Route contract passed.')
