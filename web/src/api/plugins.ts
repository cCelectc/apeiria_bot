import type {
  RawSettingsResponse,
  RawSettingsValidationResponse,
  SettingsResponse,
} from './settings'
import client from './client'

export interface PluginItem {
  module_name: string
  kind: string
  access_mode: string
  name: string | null
  description: string | null
  homepage: string | null
  source: string
  is_global_enabled: boolean
  is_protected: boolean
  protected_reason: string | null
  plugin_type: string
  admin_level: number
  author: string | null
  version: string | null
  is_loaded: boolean
  is_explicit: boolean
  is_dependency: boolean
  is_pending_uninstall: boolean
  can_edit_config: boolean
  can_view_readme: boolean
  can_enable_disable: boolean
  can_uninstall: boolean
  can_package_update: boolean
  child_plugins: string[]
  required_plugins: string[]
  dependent_plugins: string[]
  installed_package: string | null
  installed_module_names: string[]
}

export interface PluginUpdateCheckItem {
  module_name: string
  package_name: string
  current_version: string | null
  latest_version: string | null
  has_update: boolean
  checked: boolean
  error: string | null
}

export interface PluginTogglePreview {
  module_name: string
  enabled: boolean
  allowed: boolean
  summary: string
  blocked_reason: string | null
  requires_enable: string[]
  requires_disable: string[]
  protected_dependents: string[]
  missing_dependencies: string[]
}

export interface PluginToggleResult {
  module_name: string
  enabled: boolean
  affected_modules: string[]
}

export interface PluginReadmeResponse {
  module_name: string
  filename: string
  content: string
}

export interface OrphanPluginConfigItem {
  section: string
  module_name: string | null
  has_section: boolean
  reason: string
}

export interface OrphanPluginConfigResponse {
  items: OrphanPluginConfigItem[]
}

export interface PluginStoreSource {
  source_id: string
  name: string
  kind: string
  enabled: boolean
  is_builtin: boolean
  is_official: boolean
  base_url: string | null
  last_synced_at: string | null
  last_error: string | null
}

export interface PluginStoreItem {
  source_id: string
  source_name: string
  plugin_id: string
  name: string
  module_name: string
  package_name: string
  description: string | null
  project_link: string | null
  homepage: string | null
  author: string | null
  author_link: string | null
  version: string | null
  tags: string[]
  is_official: boolean
  publish_time: string | null
  extra: Record<string, unknown>
  is_installed: boolean
  is_registered: boolean
  installed_package: string | null
  installed_module_names: string[]
  can_update: boolean
}

export interface PluginStoreCategoryItem {
  value: string
  count: number
}

export interface PluginStoreItemsResponse {
  items: PluginStoreItem[]
  categories: PluginStoreCategoryItem[]
  total: number
  page: number
  per_page: number
}

export interface PluginStoreTask {
  task_id: string
  title: string
  status: string
  logs: string
  error: string | null
  result: Record<string, unknown>
  created_at: string | null
  started_at: string | null
  finished_at: string | null
}

export function getPlugins () {
  return client.get<PluginItem[]>('/plugins/')
}

export function checkPluginUpdates (payload?: { force_refresh?: boolean }) {
  return client.post<PluginUpdateCheckItem[]>(
    '/plugins/update-checks',
    payload || {},
  )
}

export function getOrphanPluginConfigs () {
  return client.get<OrphanPluginConfigResponse>('/plugins/orphan-configs')
}

export function cleanupOrphanPluginConfigs () {
  return client.post<OrphanPluginConfigResponse>(
    '/plugins/orphan-configs/cleanup',
  )
}

export function installManualPlugin (payload: {
  requirement: string
  module_name?: string
}) {
  return client.post<PluginStoreTask>('/plugins/install/manual', payload)
}

export function getPluginInstallTask (taskId: string) {
  return client.get<PluginStoreTask>(`/plugins/install/tasks/${taskId}`)
}

export function updateInstalledPlugin (
  moduleName: string,
  payload: { package_name: string },
) {
  return client.post<PluginStoreTask>(`/plugins/${moduleName}/update`, payload)
}

export function getPluginStoreSources () {
  return client.get<PluginStoreSource[]>('/plugins/store/sources')
}

export function getPluginStoreItems (params?: {
  source?: string
  search?: string
  category?: string
  sort?: string
  installed_only?: boolean
  uninstalled_only?: boolean
  page?: number
  per_page?: number
}) {
  return client.get<PluginStoreItemsResponse>('/plugins/store/items', { params })
}

export function getPluginStoreItem (sourceId: string, pluginId: string) {
  return client.get<PluginStoreItem>(
    `/plugins/store/items/${encodeURIComponent(sourceId)}/${encodeURIComponent(pluginId)}`,
  )
}

export function refreshPluginStoreSources (payload?: {
  source_id?: string
}) {
  return client.post<PluginStoreSource[]>(
    '/plugins/store/refresh',
    payload || {},
  )
}

export function installPluginStoreItem (payload: {
  source_id: string
  plugin_id: string
  package_name: string
  module_name: string
}) {
  return client.post<PluginStoreTask>('/plugins/store/install', payload)
}

export function updatePluginStoreItem (payload: {
  source_id: string
  plugin_id: string
  package_name: string
  module_name: string
}) {
  return client.post<PluginStoreTask>('/plugins/store/update', payload)
}

export function getPluginStoreTask (taskId: string) {
  return client.get<PluginStoreTask>(`/plugins/store/tasks/${taskId}`)
}

export function revertPluginStoreInstall (payload: {
  package_name: string
  module_name: string
}) {
  return client.post<{ status: string }>('/plugins/store/revert-install', payload)
}

export function getPluginSettings (moduleName: string) {
  return client.get<SettingsResponse>(`/plugins/${moduleName}/settings`)
}

export function getPluginSettingsRaw (moduleName: string) {
  return client.get<RawSettingsResponse>(`/plugins/${moduleName}/settings/raw`)
}

export function getPluginReadme (moduleName: string) {
  return client.get<PluginReadmeResponse>(`/plugins/${moduleName}/readme`)
}

export function updatePluginSettings (
  moduleName: string,
  payload: {
    values: Record<string, unknown>
    clear?: string[]
  },
) {
  return client.patch<SettingsResponse>(
    `/plugins/${moduleName}/settings`,
    payload,
  )
}

export function updatePluginSettingsRaw (
  moduleName: string,
  payload: { text: string },
) {
  return client.patch<RawSettingsResponse>(
    `/plugins/${moduleName}/settings/raw`,
    payload,
  )
}

export function validatePluginSettingsRaw (
  moduleName: string,
  payload: { text: string },
) {
  return client.post<RawSettingsValidationResponse>(
    `/plugins/${moduleName}/settings/raw/validate`,
    payload,
  )
}

export function updatePlugin (
  moduleName: string,
  enabled: boolean,
  cascade = false,
) {
  return client.patch<PluginToggleResult>(`/plugins/${moduleName}`, null, {
    params: { enabled, cascade },
  })
}

export function getPluginTogglePreview (moduleName: string, enabled: boolean) {
  return client.get<PluginTogglePreview>(
    `/plugins/${moduleName}/toggle-preview`,
    { params: { enabled } },
  )
}

export function uninstallPlugin (
  moduleName: string,
  payload?: { remove_config?: boolean },
) {
  return client.post<{ status: string, detail?: string | null }>(
    `/plugins/${encodeURIComponent(moduleName)}/uninstall`,
    payload || {},
  )
}
