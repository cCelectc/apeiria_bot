export interface SettingsChoiceItem {
  title: string
  value: unknown
}

export interface SettingsFieldSchemaFieldItem {
  key: string
  label: string
  help: string
  default: unknown
  schema: SettingsFieldSchemaItem
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
  has_local_override: boolean
  allows_null: boolean
  editable: boolean
  type_category: string
  order: number
  secret: boolean
}

export interface SettingsResponse {
  module_name: string
  section: string
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
  line?: number | null
  column?: number | null
}
