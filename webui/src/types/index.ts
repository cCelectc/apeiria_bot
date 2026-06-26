export interface Plugin {
  name: string
  source: string
  enabled: boolean
  path_or_module: string
}

export interface Adapter {
  name: string
  source: string
  enabled: boolean
  module_name: string
}

export interface ConfigField {
  key: string
  label: string
  help: string | null
  type: string
  default: unknown
  order: number
  secret: boolean
  choices: unknown[] | null
}

export interface StoreItem {
  name: string
  version: string
  description: string
  author: string
  homepage: string
  pypi_name: string
  module_names: string[]
  supported_adapters: string[]
  installed_version: string | null
}

export interface LogRecord {
  time: string
  level: string
  name: string
  message: string
}

export interface StatusInfo {
  uptime: number
  plugin_count: number
  adapters: string[]
}

export interface LogHistory {
  items: LogRecord[]
  total: number
  page: number
  size: number
}

export interface LoginResponse {
  token: string
  username: string
}
