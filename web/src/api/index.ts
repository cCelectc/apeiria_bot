import client from './client'

export interface WebUIPrincipal {
  user_id: string
  username: string
  role: string
  capabilities: string[]
}

export interface WebUIAccountItem {
  user_id: string
  username: string
  role: string
  is_disabled: boolean
  last_login_at: string | null
  password_changed_at: string | null
}

export interface SecurityAuditEventItem {
  event_type: string
  occurred_at: string
  actor_username: string | null
  target_username: string | null
  detail: string | null
}

export interface SettingsFieldItem {
  key: string
  label: string
  type: string
  editor: string
  item_type: string | null
  key_type: string | null
  schema: SettingsFieldSchemaItem | null
  default: unknown
  help: string
  choices: SettingsChoiceItem[]
  base_value: unknown
  current_value: unknown
  local_value: unknown
  value_source: string
  global_key: string | null
  has_local_override: boolean
  allows_null: boolean
  editable: boolean
  type_category: string
  order: number
  secret: boolean
}

export interface SettingsFieldSchemaFieldItem {
  key: string
  label: string
  help: string
  default: unknown
  schema: SettingsFieldSchemaItem
}

export interface SettingsChoiceItem {
  title: string
  value: unknown
}

export interface SettingsFieldSchemaItem {
  type: string
  item_type: string | null
  key_type: string | null
  choices: SettingsChoiceItem[]
  allows_null: boolean
  fields: SettingsFieldSchemaFieldItem[]
  item_schema: SettingsFieldSchemaFieldItem | null
  key_schema: SettingsFieldSchemaFieldItem | null
  value_schema: SettingsFieldSchemaFieldItem | null
}

export interface SettingsResponse {
  module_name: string
  section: string
  legacy_flatten: boolean
  config_source: string
  has_config_model: boolean
  fields: SettingsFieldItem[]
}

export interface RawSettingsResponse {
  module_name: string
  section: string
  text: string
}

export interface RawSettingsValidationResponse {
  valid: boolean
  message: string | null
  line: number | null
  column: number | null
}

export interface ModuleConfigItem {
  name: string
  is_loaded: boolean
  is_importable: boolean
}

export interface DirConfigItem {
  path: string
  exists: boolean
  is_loaded: boolean
}

export interface DriverConfigItem {
  name: string
  is_active: boolean
}

export interface DashboardStatus {
  status: string
  uptime: number
  plugins_count: number
  disabled_plugins_count: number
  groups_count: number
  disabled_groups_count: number
  access_rules_count: number
  adapters: string[]
}

export interface DashboardEventItem {
  timestamp: string
  level: string
  source: string
  message: string
}

export interface LogItem {
  timestamp: string
  level: string
  source: string
  message: string
  raw: string
  extra: Record<string, unknown>
}

export interface LogHistoryResponse {
  items: LogItem[]
  total: number
  before: number
  next_before: number | null
  has_more: boolean
}

export interface LogSourcesResponse {
  items: string[]
}

export interface LogHistoryQuery {
  before?: number
  limit?: number
  level?: string
  source?: string
  search?: string
  start?: string
  end?: string
  include_access?: boolean
}

export interface WebUIBuildStatus {
  is_built: boolean
  is_stale: boolean
  can_build: boolean
  build_tool: string | null
  detail: string | null
}

export interface WebUIBuildRunResult extends WebUIBuildStatus {
  logs: string
}

export interface WebUIBuildStreamEvent {
  event: 'chunk' | 'done' | 'error'
  chunk?: string
  detail?: string | null
  status?: WebUIBuildStatus
}

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

export interface AccessRuleItem {
  subject_type: string
  subject_id: string
  plugin_module: string
  effect: string
  note: string | null
}

export interface UserLevelItem {
  user_id: string
  group_id: string
  level: number
}

export interface AIToolItem {
  name: string
  description: string
  display_name?: string
  display_description?: string
  read_only: boolean
  concurrency_safe: boolean
  risk_level: string
  risk_label?: string
  is_capability_bridge: boolean
}

export type AISkillItem = AIToolItem

export interface AIToolPolicyBindingItem {
  binding_id: string
  scope_type: string
  scope_id: string
  allow_read_only_tools: boolean
  capability_mode: string
}

export interface AIToolExecutionItem {
  execution_id: string
  conversation_id: string
  tool_name: string
  status: string
  input_json: string | null
  output_json: string | null
  created_at: string
}

export interface AIToolIntentPreviewItem {
  tool_name: string
  kind: string
  reason: string | null
  input_payload: unknown
}

export interface AIToolPolicyPreviewItem {
  execution_enabled: boolean
  allowed_tool_names: string[] | null
  denied_tool_names: string[]
  allow_high_risk_tools: boolean
  allow_capability_bridge: boolean
}

export interface AICapabilityItem {
  capability_name: string
  bound_tool_name: string
}

export interface AICapabilityPreviewItem {
  capability_name: string
  registered: boolean
  allowed: boolean
  reason: string
  allow_capability_bridge: boolean
  execution_enabled: boolean
}

export interface AIPersonaItem {
  persona_id: string
  name: string
  description: string
  system_prompt: string
  style_prompt: string
  enabled: boolean
}

export interface AIPersonaBindingItem {
  binding_id: string
  scope_type: string
  scope_id: string
  persona_id: string
}

export interface AIMemoryItem {
  memory_id: string
  memory_domain: string
  memory_type: string
  subject_type: string
  subject_id: string
  content: string
  source_turn_id: string | null
  salience: number
  confidence: number
  last_recalled_at: string | null
  created_at: string
}

export interface AIRecentTargetItem {
  target_type: string
  subject_type: string
  subject_id: string
  title: string
  subtitle: string | null
  conversation_id: string | null
  platform: string | null
  scope_type: string | null
  scope_id: string | null
  subject_user_id: string | null
  last_active_at: string | null
}

export interface AIMemoryCreateRequest {
  memory_domain: string
  memory_type: string
  subject_type: string
  subject_id: string
  content: string
  salience?: number
  confidence?: number
}

export interface AISourcePresetItem {
  preset_type: string
  display_name: string
  capability_type: string
  client_type: string
  default_api_base: string | null
  description: string
}

export interface AISourceItem {
  source_id: string
  name: string
  capability_type: string
  client_type: string
  preset_type: string
  api_base: string | null
  api_key_env_name: string | null
  enabled: boolean
  timeout_seconds: number | null
  custom_headers: Record<string, string>
  extra_config: Record<string, unknown>
}

export interface AISourceModelItem {
  model_id: string
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
  extra_params: Record<string, unknown>
}

export interface AISourceModelTestResult {
  model_identifier: string
  content: string
  tool_call_count: number
}

export interface AIConversationItem {
  conversation_id: string
  platform: string
  bot_id: string
  scope_type: string
  scope_id: string
  subject_user_id: string | null
  short_summary: string | null
  created_at: string
  updated_at: string
  last_active_at: string
}

export interface AIConversationTurnItem {
  turn_id: string
  conversation_id: string
  sender_type: string
  sender_id: string
  content_text: string
  created_at: string
  raw_payload: Record<string, unknown> | null
  trace_id: string | null
  source_id: string | null
  model_name: string | null
  recalled_memory_count: number | null
  tool_observation_count: number | null
}

export interface AIConversationPromptPreviewItem {
  conversation_id: string
  latest_user_message: string | null
  planning_source_id: string | null
  planning_profile_id: string | null
  planning_model_name: string | null
  planning_task_class: string | null
  roleplay_source_id: string | null
  roleplay_profile_id: string | null
  roleplay_model_name: string | null
  roleplay_task_class: string | null
  source_id: string | null
  profile_id: string | null
  model_name: string | null
  persona_id: string | null
  conversation_summary: string | null
  relationship_context: string | null
  tool_policy: string | null
  social_action: string | null
  social_tool_mode: string | null
  social_reason_text: string | null
  social_reason_codes: string[]
  social_policy_source: string | null
  tool_results: string[]
  memories: AIMemoryItem[]
  social_memory_count: number
  knowledge_memory_count: number
  rendered_roleplay_prompt: string | null
  rendered_prompt: string
}

export interface AIFutureTaskItem {
  task_id: string
  conversation_id: string
  platform: string
  scope_type: string
  scope_id: string
  user_id: string | null
  title: string
  description: string
  trigger_at: string
  status: string
  source_turn_id: string | null
  scheduler_job_id: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface AIRelationshipStateItem {
  affinity_id: string
  platform: string
  group_id: string | null
  user_id: string
  score: number
  mood_tags: string[]
  last_event_at: string
}

export interface AIModelCatalogItem {
  id: string
  name: string
}

export interface AIModelProfileItem {
  profile_id: string
  name: string
  model_id: string
  task_class: string
  priority: number
  enabled: boolean
  fallback_profile_id: string | null
}

export interface AIModelBindingItem {
  binding_id: string
  scope_type: string
  scope_id: string
  profile_id: string
}

export function login (payload: {
  username: string
  password: string
}) {
  return client.post<{ token: string, principal: WebUIPrincipal }>('/auth/login', payload)
}

export function register (payload: {
  registration_code: string
  username: string
  password: string
}) {
  return client.post<{ status: string, detail?: string | null }>('/auth/register', payload)
}

export function getCurrentUser () {
  return client.get<WebUIPrincipal>('/auth/me')
}

export function getCurrentAccount () {
  return client.get<WebUIAccountItem>('/auth/me/account')
}

export function changePassword (payload: {
  current_password: string
  new_password: string
}) {
  return client.post<{ status: string, detail?: string | null, token: string, principal: WebUIPrincipal }>('/auth/password', payload)
}

export function getSecurityAuditEvents () {
  return client.get<SecurityAuditEventItem[]>('/auth/audit-events')
}

export function revokeOtherSessions () {
  return client.post<{ status: string, detail?: string | null, token: string, principal: WebUIPrincipal }>('/auth/sessions/revoke-others')
}

export function getStatus () {
  return client.get<DashboardStatus>('/dashboard/status')
}

export function getDashboardEvents () {
  return client.get<{ items: DashboardEventItem[] }>('/dashboard/events')
}

export function getWebUIBuildStatus () {
  return client.get<WebUIBuildStatus>('/dashboard/webui-build')
}

export function rebuildWebUI () {
  return client.post<WebUIBuildRunResult>('/dashboard/webui-build')
}

function clearSessionAndRedirect () {
  localStorage.removeItem('token')
  localStorage.removeItem('apeiria-principal')
  window.location.href = '/login'
}

export async function streamRebuildWebUI (
  onEvent: (event: WebUIBuildStreamEvent) => void | Promise<void>,
) {
  const token = localStorage.getItem('token')
  const response = await fetch('/api/dashboard/webui-build/stream', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })

  if (response.status === 401 || response.status === 403) {
    clearSessionAndRedirect()
    throw new Error('Unauthorized')
  }

  if (!response.ok) {
    const body = await response.text()
    let detail = body
    try {
      const payload = JSON.parse(body) as { detail?: string }
      detail = payload.detail || body
    } catch {
      // Keep plain-text error bodies as-is.
    }
    throw new Error(detail || 'Failed to rebuild WebUI')
  }

  if (!response.body) {
    throw new Error('Build log stream unavailable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    let lineBreakIndex = buffer.indexOf('\n')
    while (lineBreakIndex >= 0) {
      const line = buffer.slice(0, lineBreakIndex).trim()
      buffer = buffer.slice(lineBreakIndex + 1)
      if (line) {
        await onEvent(JSON.parse(line) as WebUIBuildStreamEvent)
      }
      lineBreakIndex = buffer.indexOf('\n')
    }

    if (done) {
      const line = buffer.trim()
      if (line) {
        await onEvent(JSON.parse(line) as WebUIBuildStreamEvent)
      }
      break
    }
  }
}

export function restartBot () {
  return client.post<{ status: string, detail?: string | null }>('/dashboard/restart')
}

export function getLogHistory (params?: LogHistoryQuery,
  signal?: AbortSignal) {
  return client.get<LogHistoryResponse>('/logs/history', { params, signal })
}

export function getLogSources (signal?: AbortSignal) {
  return client.get<LogSourcesResponse>('/logs/sources', { signal })
}

export function getPlugins () {
  return client.get<PluginItem[]>('/plugins/')
}

export function checkPluginUpdates (payload?: { force_refresh?: boolean }) {
  return client.post<PluginUpdateCheckItem[]>('/plugins/update-checks', payload || {})
}

export function getOrphanPluginConfigs () {
  return client.get<OrphanPluginConfigResponse>('/plugins/orphan-configs')
}

export function cleanupOrphanPluginConfigs () {
  return client.post<OrphanPluginConfigResponse>('/plugins/orphan-configs/cleanup')
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

export function updateInstalledPlugin (moduleName: string,
  payload: { package_name: string }) {
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
  return client.get<PluginStoreItem>(`/plugins/store/items/${encodeURIComponent(sourceId)}/${encodeURIComponent(pluginId)}`)
}

export function refreshPluginStoreSources (payload?: {
  source_id?: string
}) {
  return client.post<PluginStoreSource[]>('/plugins/store/refresh', payload || {})
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

export function getCoreSettings () {
  return client.get<SettingsResponse>('/plugins/core/settings')
}

export function getCoreSettingsRaw () {
  return client.get<RawSettingsResponse>('/plugins/core/settings/raw')
}

export function updateCoreSettings (payload: {
  values: Record<string, unknown>
  clear?: string[]
}) {
  return client.patch<SettingsResponse>('/plugins/core/settings', payload)
}

export function updateCoreSettingsRaw (payload: { text: string }) {
  return client.patch<RawSettingsResponse>('/plugins/core/settings/raw', payload)
}

export function validateCoreSettingsRaw (payload: { text: string }) {
  return client.post<RawSettingsValidationResponse>('/plugins/core/settings/raw/validate', payload)
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

export function updatePluginSettings (moduleName: string,
  payload: {
    values: Record<string, unknown>
    clear?: string[]
  }) {
  return client.patch<SettingsResponse>(`/plugins/${moduleName}/settings`, payload)
}

export function updatePluginSettingsRaw (moduleName: string,
  payload: { text: string }) {
  return client.patch<RawSettingsResponse>(`/plugins/${moduleName}/settings/raw`, payload)
}

export function validatePluginSettingsRaw (moduleName: string,
  payload: { text: string }) {
  return client.post<RawSettingsValidationResponse>(`/plugins/${moduleName}/settings/raw/validate`, payload)
}

export function getPluginConfig () {
  return client.get<{
    modules: ModuleConfigItem[]
    dirs: DirConfigItem[]
  }>('/plugins/config')
}

export function getAdapterConfig () {
  return client.get<{ modules: ModuleConfigItem[] }>('/plugins/adapters/config')
}

export function updateAdapterConfig (payload: { modules: string[] }) {
  return client.patch<{ modules: ModuleConfigItem[] }>('/plugins/adapters/config', payload)
}

export function getDriverConfig () {
  return client.get<{ builtin: DriverConfigItem[] }>('/plugins/drivers/config')
}

export function updateDriverConfig (payload: { builtin: string[] }) {
  return client.patch<{ builtin: DriverConfigItem[] }>('/plugins/drivers/config', payload)
}

export function updatePluginConfig (payload: {
  modules: string[]
  dirs: string[]
}) {
  return client.patch<{
    modules: ModuleConfigItem[]
    dirs: DirConfigItem[]
  }>('/plugins/config', payload)
}

export function updatePlugin (moduleName: string,
  enabled: boolean,
  cascade = false) {
  return client.patch<PluginToggleResult>(`/plugins/${moduleName}`, null, {
    params: { enabled, cascade },
  })
}

export function getPluginTogglePreview (moduleName: string, enabled: boolean) {
  return client.get<PluginTogglePreview>(`/plugins/${moduleName}/toggle-preview`, {
    params: { enabled },
  })
}

export function uninstallPlugin (moduleName: string,
  payload?: { remove_config?: boolean }) {
  return client.post<{ status: string, detail?: string | null }>(
    `/plugins/${encodeURIComponent(moduleName)}/uninstall`,
    payload || {},
  )
}

export function getAccessRules () {
  return client.get<AccessRuleItem[]>('/permissions/rules')
}

export function createAccessRule (payload: {
  subject_type: string
  subject_id: string
  plugin_module: string
  effect: string
  note?: string | null
}) {
  return client.post<AccessRuleItem>('/permissions/rules', payload)
}

export function deleteAccessRule (payload: {
  subject_type: string
  subject_id: string
  plugin_module: string
}) {
  return client.post('/permissions/rules/delete', payload)
}

export function updatePluginAccessMode (moduleName: string,
  accessMode: string) {
  return client.patch('/permissions/plugins/' + encodeURIComponent(moduleName) + '/access-mode', {
    access_mode: accessMode,
  })
}

export function getUsers () {
  return client.get<UserLevelItem[]>('/permissions/users')
}

export function updateUserLevel (userId: string, groupId: string, level: number) {
  return client.patch(`/permissions/users/${userId}`, { level }, {
    params: { group_id: groupId },
  })
}

export function getAITools () {
  return client.get<AIToolItem[]>('/ai/tools')
}

export function getAISkills () {
  return client.get<AISkillItem[]>('/ai/skills')
}

export function getAIPersonas () {
  return client.get<AIPersonaItem[]>('/ai/personas')
}

export function getAIPersonaBindings () {
  return client.get<AIPersonaBindingItem[]>('/ai/persona-bindings')
}

export function upsertAIPersona (payload: {
  persona_id?: string | null
  name: string
  description: string
  system_prompt: string
  style_prompt: string
  enabled: boolean
}) {
  return client.put<AIPersonaItem | null>('/ai/personas', payload)
}

export function getAISourcePresets () {
  return client.get<AISourcePresetItem[]>('/ai/source-presets')
}

export function getAISources () {
  return client.get<AISourceItem[]>('/ai/sources')
}

export function createAISource (payload: {
  name: string
  capability_type: string
  preset_type: string
  api_base?: string | null
  api_key_env_name?: string | null
  enabled: boolean
  timeout_seconds?: number | null
  custom_headers?: Record<string, string>
  extra_config?: Record<string, unknown>
}) {
  return client.post<AISourceItem>('/ai/sources', payload)
}

export function updateAISource (payload: {
  source_id: string
  name: string
  capability_type: string
  preset_type: string
  api_base?: string | null
  api_key_env_name?: string | null
  enabled: boolean
  timeout_seconds?: number | null
  custom_headers?: Record<string, string>
  extra_config?: Record<string, unknown>
}) {
  return client.put<AISourceItem | null>('/ai/sources', payload)
}

export function deleteAISource (sourceId: string) {
  return client.delete<boolean>('/ai/sources', { params: { source_id: sourceId } })
}

export function getAISourceModels (sourceId: string) {
  return client.get<AISourceModelItem[]>('/ai/sources/models', { params: { source_id: sourceId } })
}

export function fetchAISourceModels (payload: {
  source_id?: string | null
  preset_type?: string | null
  api_base?: string | null
  api_key_env_name?: string | null
  api_key?: string | null
  extra_config?: Record<string, unknown>
}) {
  return client.post<AIModelCatalogItem[]>('/ai/sources/models/fetch', payload)
}

export function testAISourceModel (payload: {
  source_id?: string | null
  preset_type?: string | null
  api_base?: string | null
  api_key_env_name?: string | null
  api_key?: string | null
  extra_config?: Record<string, unknown>
  model_identifier: string
}) {
  return client.post<AISourceModelTestResult>('/ai/sources/models/test', payload)
}

export function createAISourceModel (payload: {
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
  extra_params?: Record<string, unknown>
}) {
  return client.post<AISourceModelItem>('/ai/sources/models', payload)
}

export function updateAISourceModel (payload: {
  model_id: string
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
  extra_params?: Record<string, unknown>
}) {
  return client.put<AISourceModelItem | null>('/ai/sources/models', payload)
}

export function deleteAISourceModel (modelId: string, sourceId?: string) {
  return client.delete<boolean>('/ai/sources/models', {
    params: {
      model_id: modelId,
      source_id: sourceId,
    },
  })
}

export function getAIModelProfiles () {
  return client.get<AIModelProfileItem[]>('/ai/model-profiles')
}

export function upsertAIModelProfile (payload: {
  profile_id?: string | null
  name: string
  model_id: string
  task_class: string
  priority: number
  enabled: boolean
  fallback_profile_id?: string | null
}) {
  return client.put<AIModelProfileItem | null>('/ai/model-profiles', payload)
}

export function getAIModelBindings () {
  return client.get<AIModelBindingItem[]>('/ai/model-bindings')
}

export function getAIMemories (params: {
  subject_type: string
  subject_id: string
  memory_domain?: string
  query?: string
  limit?: number
}) {
  return client.get<AIMemoryItem[]>('/ai/memories', { params })
}

export function createAIMemory (payload: AIMemoryCreateRequest) {
  return client.post<AIMemoryItem>('/ai/memories', payload)
}

export function updateAIMemory (payload: {
  memory_id: string
  content: string
  salience: number
  confidence: number
}) {
  return client.patch<AIMemoryItem | null>('/ai/memories', payload)
}

export function deleteAIMemory (memoryId: string) {
  return client.delete<{ deleted: boolean }>('/ai/memories', {
    params: { memory_id: memoryId },
  })
}

export function getAIRecentTargets (params?: {
  limit?: number
}) {
  return client.get<AIRecentTargetItem[]>('/ai/recent-targets', { params })
}

export function getAIConversations (params?: {
  limit?: number
}) {
  return client.get<AIConversationItem[]>('/ai/conversations', { params })
}

export function getAIConversationTurns (params: {
  conversation_id: string
  limit?: number
}) {
  return client.get<AIConversationTurnItem[]>('/ai/conversations/turns', { params })
}

export function getAIConversationPromptPreview (params: {
  conversation_id: string
  turn_limit?: number
}) {
  return client.get<AIConversationPromptPreviewItem | null>('/ai/conversations/prompt-preview', { params })
}

export function getAIFutureTasks (params?: {
  limit?: number
}) {
  return client.get<AIFutureTaskItem[]>('/ai/future-tasks', { params })
}

export function cancelAIFutureTask (taskId: string) {
  return client.delete<AIFutureTaskItem | null>('/ai/future-tasks', {
    params: { task_id: taskId },
  })
}

export function getAIRelationshipStates (params?: {
  limit?: number
}) {
  return client.get<AIRelationshipStateItem[]>('/ai/relationships/list', { params })
}

export function getAIRelationshipState (params: {
  platform: string
  user_id: string
  group_id?: string
}) {
  return client.get<AIRelationshipStateItem>('/ai/relationships', { params })
}

export function updateAIRelationshipScore (payload: {
  platform: string
  user_id: string
  group_id?: string | null
  score: number
}) {
  return client.patch<AIRelationshipStateItem>('/ai/relationships', payload)
}

export function getAICapabilities () {
  return client.get<AICapabilityItem[]>('/ai/tools/capabilities')
}

export function getAIToolExecutions (params: {
  conversation_id: string
}) {
  return client.get<AIToolExecutionItem[]>('/ai/tools/executions', { params })
}

export function getAIToolPolicyBindings () {
  return client.get<AIToolPolicyBindingItem[]>('/ai/tools/policy-bindings')
}

export function createAIToolPolicyBinding (payload: {
  scope_type: string
  scope_id: string
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolPolicyBindingItem>('/ai/tools/policy-bindings', payload)
}

export function updateAIToolPolicyBinding (payload: {
  binding_id: string
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.patch<AIToolPolicyBindingItem | null>('/ai/tools/policy-bindings', payload)
}

export function deleteAIToolPolicyBinding (bindingId: string) {
  return client.delete<{ deleted: boolean }>('/ai/tools/policy-bindings', {
    params: { binding_id: bindingId },
  })
}

export function previewAIToolPolicy (payload: {
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolPolicyPreviewItem>('/ai/tools/policy-preview', payload)
}

export function previewAIToolIntents (payload: {
  message_text: string
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolIntentPreviewItem[]>('/ai/tools/intent-preview', payload)
}

export function previewAISkillPolicyDebug (payload: {
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolPolicyPreviewItem>('/ai/debug/skills/policy-preview', payload)
}

export function previewAICapability (payload: {
  capability_name: string
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AICapabilityPreviewItem>('/ai/tools/capability-preview', payload)
}

export function previewAISkillCapabilityDebug (payload: {
  capability_name: string
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AICapabilityPreviewItem>('/ai/debug/skills/capability-preview', payload)
}
