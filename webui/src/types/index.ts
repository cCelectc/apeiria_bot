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

export interface ConfigContract {
  namespace: string | null
  is_scoped: boolean
  owner_kind: 'plugin' | 'adapter' | 'nonebot' | 'apeiria'
  owner_id: string
  source: 'pydantic' | 'extra_only' | 'none'
  fields: FieldNode[]
  json_schema: Record<string, unknown>
}

export type FieldNode = PrimitiveField | ObjectField | ArrayField | MapField | AnyField

export interface PrimitiveField {
  kind: 'primitive'
  key: string
  label: string
  description: string
  type: 'str' | 'int' | 'float' | 'bool' | 'enum' | 'literal'
  default: unknown
  required: boolean
  secret: boolean
  choices?: { value: string; label: string }[]
  order: number
}

export interface ObjectField {
  kind: 'object'
  key: string
  label: string
  description: string
  children: FieldNode[]
  default: Record<string, unknown> | null
  order: number
}

export interface ArrayField {
  kind: 'array'
  key: string
  label: string
  description: string
  item_schema: FieldNode | null
  default: unknown[] | null
  order: number
}

export interface MapField {
  kind: 'map'
  key: string
  label: string
  description: string
  key_type: string
  value_schema: FieldNode | null
  order: number
}

export interface AnyField {
  kind: 'any'
  key: string
  label: string
  description: string
  default: unknown
  order: number
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
