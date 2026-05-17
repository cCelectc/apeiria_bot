import client from './client'

export interface AdapterConfigItem {
  name: string
  is_loaded: boolean
  is_importable: boolean
}

export interface AdapterStoreSource {
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

export interface AdapterStoreItem {
  source_id: string
  source_name: string
  adapter_id: string
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

export interface AdapterStoreCategoryItem {
  value: string
  count: number
}

export interface AdapterStoreItemsResponse {
  items: AdapterStoreItem[]
  categories: AdapterStoreCategoryItem[]
  total: number
  page: number
  per_page: number
}

export interface AdapterStoreTask {
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
  steps: AdapterTaskStep[]
  diagnostics: AdapterTaskDiagnostic[]
}

export interface AdapterTaskStep {
  phase: string | null
  label: string | null
  status: string | null
  detail: string | null
  command: string | null
  output_excerpt: string | null
  started_at: string | null
  finished_at: string | null
}

export interface AdapterTaskDiagnostic {
  phase?: string
  message?: string
  [key: string]: unknown
}

export function getAdapterConfig() {
  return client.get<{ modules: AdapterConfigItem[] }>('/plugins/adapters/config')
}

export function updateAdapterConfig(payload: { modules: string[] }) {
  return client.patch<{ modules: AdapterConfigItem[] }>(
    '/plugins/adapters/config',
    payload,
  )
}

export function getAdapterStoreSources() {
  return client.get<AdapterStoreSource[]>('/adapters/store/sources')
}

export function getAdapterStoreItems(params?: {
  source?: string
  search?: string
  category?: string
  sort?: string
  installed_only?: boolean
  uninstalled_only?: boolean
  page?: number
  per_page?: number
}) {
  return client.get<AdapterStoreItemsResponse>('/adapters/store/items', { params })
}

export function getAdapterStoreItem(sourceId: string, adapterId: string) {
  return client.get<AdapterStoreItem>(
    `/adapters/store/items/${encodeURIComponent(sourceId)}/${encodeURIComponent(adapterId)}`,
  )
}

export function refreshAdapterStoreSources(payload?: { source_id?: string }) {
  return client.post<AdapterStoreSource[]>(
    '/adapters/store/refresh',
    payload || {},
  )
}

export function installAdapterStoreItem(payload: {
  source_id: string
  adapter_id: string
  package_name: string
  module_name: string
}) {
  return client.post<AdapterStoreTask>('/adapters/store/install', payload)
}

export function installManualAdapter(payload: {
  requirement: string
  module_name?: string
}) {
  return client.post<AdapterStoreTask>('/adapters/store/install/manual', payload)
}

export function updateAdapterStoreItem(payload: {
  source_id: string
  adapter_id: string
  package_name: string
  module_name: string
}) {
  return client.post<AdapterStoreTask>('/adapters/store/update', payload)
}

export function uninstallAdapterStoreItem(payload: {
  package_name: string
  module_name: string
}) {
  return client.post<AdapterStoreTask>('/adapters/store/uninstall', payload)
}

export function getAdapterStoreTask(taskId: string) {
  return client.get<AdapterStoreTask>(`/adapters/store/tasks/${taskId}`)
}

export function revertAdapterStoreInstall(payload: {
  package_name: string
  module_name: string
}) {
  return client.post<{ status: string }>('/adapters/store/revert-install', payload)
}
