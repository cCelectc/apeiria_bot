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

export type PluginEffectiveState =
  | 'active'
  | 'execution_blocked'
  | 'disabled'
  | 'not_loaded'
  | 'pending_uninstall'

export interface PluginWorkbenchPolicyState {
  enabled: boolean
  can_change: boolean
  locked_reason: string | null
}

export interface PluginWorkbenchRuntimeState {
  loaded: boolean
  execution_blocked: boolean
}

export interface PluginWorkbenchStartupState {
  will_load: boolean
  requires_restart_to_apply_fully: boolean
}

export interface PluginWorkbenchCapabilities {
  can_edit_settings: boolean
  can_view_readme: boolean
  can_enable_disable: boolean
  can_uninstall: boolean
  can_update_package: boolean
}

export interface PluginWorkbenchItem extends PluginItem {
  display_name: string
  policy: PluginWorkbenchPolicyState
  runtime: PluginWorkbenchRuntimeState
  startup: PluginWorkbenchStartupState
  effective_state: PluginEffectiveState
  capabilities: PluginWorkbenchCapabilities
}

export interface PluginWorkbenchSummary {
  total: number
  enabled: number
  disabled: number
  blocked: number
  not_loaded: number
  pending_restart: number
  protected: number
}

export interface PluginWorkbenchMaintenance {
  orphan_config_count: number
  active_package_task: {
    task_id: string
    title: string
    status: string
    operation: string | null
    resource_kind: string | null
  } | null
}

export interface PluginWorkbenchResponse {
  plugins: PluginWorkbenchItem[]
  summary: PluginWorkbenchSummary
  maintenance: PluginWorkbenchMaintenance
}

export interface PluginToggleResult {
  module_name: string
  enabled: boolean
  affected_modules: string[]
}

export interface PluginPolicyUpdateResult {
  module_name: string
  policy: {
    enabled: boolean
  }
  affected_modules: string[]
  runtime_effect: string
  startup_effect: string
  restart_required: boolean
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

export interface PluginReadmeResponse {
  module_name: string
  filename: string
  content: string
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

export interface OrphanPluginConfigItem {
  section: string
  module_name: string | null
  has_section: boolean
  reason: string
}

export interface OrphanPluginConfigResponse {
  items: OrphanPluginConfigItem[]
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
  operation: string | null
  resource_kind: string | null
  requirement: string | null
  binding_value: string | null
  current_phase: string | null
  current_phase_label: string | null
  progress_percent: number | null
  queue_position: number | null
  lock_wait_started_at: string | null
  lock_acquired_at: string | null
  restart_required: boolean
  steps: PackageTaskStep[]
  diagnostics: PackageTaskDiagnostic[]
}

export type PluginInstallSourceKind = 'store_item' | 'requirement' | 'local_path'
export type PluginInstallResolutionStatus =
  | 'resolved'
  | 'ambiguous'
  | 'unresolved'
  | 'invalid'
  | 'installed'

export interface PluginInstallSource {
  kind: PluginInstallSourceKind
  value?: string | null
  source_id?: string | null
  item_id?: string | null
}

export interface PluginInstallCandidate {
  module_name: string
  kind: 'module' | 'directory'
  confidence: 'high' | 'medium' | 'low'
  reason: string
  already_registered: boolean
  already_loaded: boolean
}

export interface PluginInstallAction {
  kind: 'install_package' | 'register_local_module' | 'register_local_directory'
  requirement?: string | null
  module_name?: string | null
  path?: string | null
}

export interface PluginInstallResolution {
  source: PluginInstallSource
  status: PluginInstallResolutionStatus
  candidates: PluginInstallCandidate[]
  default_action: PluginInstallAction | null
  warnings: string[]
}

export interface PackageTaskStep {
  phase: string | null
  label: string | null
  status: string | null
  detail: string | null
  command: string | null
  output_excerpt: string | null
  started_at: string | null
  finished_at: string | null
}

export interface PackageTaskDiagnostic {
  phase?: string
  message?: string
  [key: string]: unknown
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

export interface PluginsResponse {
  items: PluginItem[]
}

export function getPlugins() {
  return client.get<PluginItem[] | PluginsResponse>('/plugins/')
}

export function getPluginWorkbench() {
  return client.get<PluginWorkbenchResponse>('/plugins/workbench')
}

export function normalizePluginsResponse(data: unknown): PluginItem[] {
  if (Array.isArray(data)) {
    return data as PluginItem[]
  }
  if (data && typeof data === 'object' && Array.isArray((data as PluginsResponse).items)) {
    return (data as PluginsResponse).items
  }
  return []
}

export function checkPluginUpdates(payload?: { force_refresh?: boolean }) {
  return client.post<PluginUpdateCheckItem[]>(
    '/plugins/update-checks',
    payload || {},
  )
}

export function getOrphanPluginConfigs() {
  return client.get<OrphanPluginConfigResponse>('/plugins/orphan-configs')
}

export function cleanupOrphanPluginConfigs() {
  return client.post<OrphanPluginConfigResponse>(
    '/plugins/orphan-configs/cleanup',
  )
}

export function installManualPlugin(payload: {
  requirement: string
  module_name?: string
}) {
  return client.post<PluginStoreTask>('/plugins/install/manual', payload)
}

export function resolvePluginInstallSource(payload: {
  source: PluginInstallSource
}) {
  return client.post<PluginInstallResolution>('/plugins/install/resolve', payload)
}

export function confirmPluginInstall(payload: {
  source: PluginInstallSource
  action: PluginInstallAction
}) {
  return client.post<PluginStoreTask>('/plugins/install/confirm', payload)
}

export function getPluginInstallTask(taskId: string) {
  return client.get<PluginStoreTask>(`/plugins/install/tasks/${taskId}`)
}

export function updateInstalledPlugin(
  moduleName: string,
  payload: { package_name: string },
) {
  return client.post<PluginStoreTask>(
    `/plugins/${encodeURIComponent(moduleName)}/update`,
    payload,
  )
}

export function uninstallPlugin(
  moduleName: string,
  payload?: { remove_config?: boolean },
) {
  return client.post<{ status: string, detail?: string | null }>(
    `/plugins/${encodeURIComponent(moduleName)}/uninstall`,
    payload || {},
  )
}

export function getPluginStoreSources() {
  return client.get<PluginStoreSource[]>('/plugins/store/sources')
}

export function getPluginStoreItems(params?: {
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

export function getPluginStoreItem(sourceId: string, pluginId: string) {
  return client.get<PluginStoreItem>(
    `/plugins/store/items/${encodeURIComponent(sourceId)}/${encodeURIComponent(pluginId)}`,
  )
}

export function refreshPluginStoreSources(payload?: { source_id?: string }) {
  return client.post<PluginStoreSource[]>(
    '/plugins/store/refresh',
    payload || {},
  )
}

export function installPluginStoreItem(payload: {
  source_id: string
  plugin_id: string
  package_name: string
  module_name: string
}) {
  return client.post<PluginStoreTask>('/plugins/store/install', payload)
}

export function updatePluginStoreItem(payload: {
  source_id: string
  plugin_id: string
  package_name: string
  module_name: string
}) {
  return client.post<PluginStoreTask>('/plugins/store/update', payload)
}

export function getPluginStoreTask(taskId: string) {
  return client.get<PluginStoreTask>(`/plugins/store/tasks/${taskId}`)
}

export function getPluginReadme(moduleName: string) {
  return client.get<PluginReadmeResponse>(`/plugins/${moduleName}/readme`)
}

export function getPluginSettings(moduleName: string) {
  return client.get<SettingsResponse>(`/plugins/${moduleName}/settings`)
}

export function getPluginSettingsRaw(moduleName: string) {
  return client.get<RawSettingsResponse>(`/plugins/${moduleName}/settings/raw`)
}

export function updatePluginSettings(
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

export function updatePluginSettingsRaw(
  moduleName: string,
  payload: { text: string },
) {
  return client.patch<RawSettingsResponse>(
    `/plugins/${moduleName}/settings/raw`,
    payload,
  )
}

export function validatePluginSettingsRaw(
  moduleName: string,
  payload: { text: string },
) {
  return client.post<RawSettingsValidationResponse>(
    `/plugins/${moduleName}/settings/raw/validate`,
    payload,
  )
}

export function updatePlugin(
  moduleName: string,
  enabled: boolean,
  cascade = false,
) {
  return client.patch<PluginPolicyUpdateResult>(
    `/plugins/${moduleName}/policy`,
    { enabled, cascade },
  )
}

export function getPluginTogglePreview(moduleName: string, enabled: boolean) {
  return client.get<PluginTogglePreview>(
    `/plugins/${moduleName}/toggle-preview`,
    { params: { enabled } },
  )
}

export function revertPluginStoreInstall(payload: {
  package_name: string
  module_name: string
}) {
  return client.post<{ status: string }>('/plugins/store/revert-install', payload)
}
