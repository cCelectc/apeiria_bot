export type SettingsFieldType =
  | "string"
  | "integer"
  | "float"
  | "boolean"
  | "object"
  | "array"
  | "mapping"
  | "enum"
  | "select"
  | "json"
  | "toml"
  | "chips"

export interface SettingsFieldMeta {
  options?: { label: string; value: string }[]
  min?: number
  max?: number
  step?: number
  unit?: string
  placeholder?: string
}

export interface SettingsFieldItem {
  key: string
  type: SettingsFieldType
  label: string
  description?: string
  placeholder?: string
  default?: unknown
  nullable?: boolean
  immutable?: boolean
  children?: SettingsFieldItem[]
  meta?: SettingsFieldMeta
}
