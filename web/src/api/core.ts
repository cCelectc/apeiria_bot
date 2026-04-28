import type {
  RawSettingsResponse,
  RawSettingsValidationResponse,
  SettingsResponse,
} from './settings'
import client from './client'

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
  return client.post<RawSettingsValidationResponse>(
    '/plugins/core/settings/raw/validate',
    payload,
  )
}

export function getPluginConfig () {
  return client.get<{
    modules: ModuleConfigItem[]
    dirs: DirConfigItem[]
  }>('/plugins/config')
}

export function getDriverConfig () {
  return client.get<{ builtin: DriverConfigItem[] }>('/plugins/drivers/config')
}

export function updateDriverConfig (payload: { builtin: string[] }) {
  return client.patch<{ builtin: DriverConfigItem[] }>(
    '/plugins/drivers/config',
    payload,
  )
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
