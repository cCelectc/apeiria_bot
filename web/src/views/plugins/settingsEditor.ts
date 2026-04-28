export interface PluginSettingChoice {
  title: string
  value: unknown
}

export interface PluginSettingSchemaField {
  key: string
  label: string
  help: string
  default: unknown
  schema: PluginSettingSchema
}

export interface PluginSettingSchema {
  type: string
  item_type: string | null
  key_type: string | null
  choices: PluginSettingChoice[]
  allows_null: boolean
  fields: PluginSettingSchemaField[]
  item_schema: PluginSettingSchemaField | null
  key_schema: PluginSettingSchemaField | null
  value_schema: PluginSettingSchemaField | null
}

export interface PluginSettingField {
  key: string
  label: string
  type: string
  editor: string
  item_type: string | null
  key_type: string | null
  schema: PluginSettingSchema | null
  default: unknown
  help: string
  choices: PluginSettingChoice[]
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

export interface PluginSettingsState {
  module_name: string
  section: string
  config_source: string
  has_config_model: boolean
  fields: PluginSettingField[]
}

export interface SettingsPreviewItem {
  key: string
  current: string
  next: string
}

export interface SettingsUpdatePayload {
  values: Record<string, unknown>
  clear: string[]
}

export function displayFieldValue (value: unknown) {
  if (value == null) {
    return 'null'
  }
  if (typeof value === 'string') {
    return value
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

export function displayChoiceTitle (choice: PluginSettingChoice) {
  return choice.title || displayFieldValue(choice.value)
}

export function isSequenceChipField (field: PluginSettingField) {
  return field.editor === 'chips'
}

export function isTextInputField (field: PluginSettingField) {
  return field.editor === 'input'
}

export function isNestedEditorField (field: PluginSettingField) {
  return field.editor === 'nested_object'
    || field.editor === 'nested_sequence'
    || field.editor === 'nested_mapping'
}

export function textInputType (field: PluginSettingField) {
  if (field.secret) {
    return 'password'
  }
  return field.type === 'int' || field.type === 'float' ? 'number' : 'text'
}

export function isNullableBoolField (field: PluginSettingField) {
  return field.type === 'bool' && field.allows_null
}

export function cloneSettingValue<T> (value: T): T {
  if (Array.isArray(value)) {
    return value.map(item => cloneSettingValue(item)) as T
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, cloneSettingValue(item)]),
    ) as T
  }
  return value
}

export function buildSchemaDefaultValue (schema: PluginSettingSchema | null): unknown {
  if (!schema) {
    return ''
  }
  if (schema.allows_null) {
    return null
  }
  if (schema.type === 'bool') {
    return false
  }
  if (schema.type === 'int' || schema.type === 'float') {
    return ''
  }
  if (schema.type === 'list' || schema.type === 'set') {
    return []
  }
  if (schema.type === 'dict') {
    return {}
  }
  if (schema.fields.length > 0) {
    return Object.fromEntries(
      schema.fields.map(field => [
        field.key,
        field.default == null ? buildSchemaDefaultValue(field.schema) : cloneSettingValue(field.default),
      ]),
    )
  }
  return ''
}

export function buildSchemaFieldDefaultValue (field: PluginSettingSchemaField): unknown {
  return field.default == null ? buildSchemaDefaultValue(field.schema) : cloneSettingValue(field.default)
}

export function toEditorValue (field: PluginSettingField, sourceValue: unknown) {
  if (sourceValue == null && field.allows_null) {
    return null
  }
  if (field.type === 'bool') {
    return typeof sourceValue === 'boolean' ? sourceValue : false
  }
  if (field.type === 'int' || field.type === 'float') {
    return sourceValue ?? ''
  }
  if (isNestedEditorField(field) && field.schema) {
    return cloneSettingValue(sourceValue ?? buildSchemaDefaultValue(field.schema))
  }
  if (field.type_category === 'sequence') {
    const value = Array.isArray(sourceValue) ? [...valueOrEmptyArray(sourceValue)] : []
    return isSequenceChipField(field) ? value : JSON.stringify(value, null, 2)
  }
  if (field.type_category === 'mapping') {
    return JSON.stringify(sourceValue ?? {}, null, 2)
  }
  return sourceValue ?? ''
}

function valueOrEmptyArray (value: unknown) {
  return Array.isArray(value) ? value : []
}

export function buildSettingsForm (fields: PluginSettingField[]) {
  const next: Record<string, unknown> = {}
  for (const field of fields) {
    next[field.key] = buildFieldFormValue(field)
  }
  return next
}

export function buildFieldFormValue (field: PluginSettingField) {
  const sourceValue = field.has_local_override ? field.local_value : null
  return toEditorValue(field, sourceValue)
}

export function buildOverrideInitialValue (field: PluginSettingField) {
  return toEditorValue(field, field.current_value ?? field.default)
}

export function buildClearedFieldValue (field: PluginSettingField) {
  return toEditorValue(field, field.base_value)
}

function coercePrimitiveValue (typeName: string | null, value: unknown) {
  if (typeName === 'int') {
    if (typeof value !== 'number' || !Number.isInteger(value)) {
      throw new TypeError('invalid int')
    }
    return value
  }
  if (typeName === 'float') {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      throw new TypeError('invalid float')
    }
    return value
  }
  if (typeName === 'bool') {
    if (typeof value === 'boolean') {
      return value
    }
    throw new Error('invalid bool')
  }
  if (value == null) {
    return null
  }
  return String(value)
}

function normalizeScalarNumberValue (
  typeName: 'int' | 'float',
  rawValue: unknown,
) {
  if (rawValue === null) {
    return null
  }
  const numericValue
    = typeof rawValue === 'number'
      ? rawValue
      : (typeof rawValue === 'string' && rawValue.trim()
          ? Number(rawValue)
          : Number.NaN)

  if (typeName === 'int') {
    if (!Number.isInteger(numericValue)) {
      throw new TypeError('invalid int')
    }
    return numericValue
  }
  if (!Number.isFinite(numericValue)) {
    throw new TypeError('invalid float')
  }
  return numericValue
}

function normalizeSequenceValue (field: PluginSettingField, rawValue: unknown) {
  if (rawValue == null && field.allows_null) {
    return null
  }
  let values: unknown[] = []
  if (isSequenceChipField(field)) {
    values = Array.isArray(rawValue) ? rawValue : []
  } else {
    if (typeof rawValue !== 'string' || !rawValue.trim()) {
      return null
    }
    const parsed = JSON.parse(rawValue)
    if (!Array.isArray(parsed)) {
      throw new TypeError('invalid array')
    }
    values = parsed
  }
  return values
    .map(item => coercePrimitiveValue(field.item_type, item))
    .filter(item => item !== '')
}

function normalizeBySchema (
  schema: PluginSettingSchema,
  rawValue: unknown,
): unknown {
  if (rawValue == null) {
    if (schema.allows_null) {
      return null
    }
    throw new Error('null not allowed')
  }

  if (schema.choices.length > 0) {
    const normalized = normalizeScalarLike(schema.type, rawValue)
    if (!schema.choices.some(choice => JSON.stringify(choice.value) === JSON.stringify(normalized))) {
      throw new Error('invalid choice')
    }
    return normalized
  }

  if (schema.type === 'bool') {
    if (typeof rawValue === 'boolean') {
      return rawValue
    }
    throw new Error('invalid bool')
  }
  if (schema.type === 'int') {
    return normalizeScalarNumberValue('int', rawValue)
  }
  if (schema.type === 'float') {
    return normalizeScalarNumberValue('float', rawValue)
  }
  if (schema.type === 'list' || schema.type === 'set') {
    if (!Array.isArray(rawValue)) {
      throw new TypeError('invalid array')
    }
    const itemSchema = schema.item_schema?.schema
    const normalized = itemSchema
      ? rawValue.map(item => normalizeBySchema(itemSchema, item))
      : rawValue
    return schema.type === 'set'
      ? Array.from(new Map(normalized.map(item => [JSON.stringify(item), item])).values())
      : normalized
  }
  if (schema.type === 'dict') {
    if (!isPlainObject(rawValue)) {
      throw new Error('invalid object')
    }
    const valueSchema = schema.value_schema?.schema
    return Object.fromEntries(
      Object.entries(rawValue).map(([key, value]) => [
        String(key),
        valueSchema ? normalizeBySchema(valueSchema, value) : value,
      ]),
    )
  }
  if (schema.fields.length > 0) {
    if (!isPlainObject(rawValue)) {
      throw new Error('invalid object')
    }
    const allowed = new Map(schema.fields.map(field => [field.key, field]))
    return Object.fromEntries(
      Object.entries(rawValue).map(([key, value]) => {
        const field = allowed.get(key)
        if (!field) {
          throw new Error(`unknown field ${key}`)
        }
        return [key, normalizeBySchema(field.schema, value)]
      }),
    )
  }
  return normalizeScalarLike(schema.type, rawValue)
}

function normalizeScalarLike (typeName: string, rawValue: unknown) {
  if (typeName === 'int') {
    return normalizeScalarNumberValue('int', rawValue)
  }
  if (typeName === 'float') {
    return normalizeScalarNumberValue('float', rawValue)
  }
  if (typeName === 'bool') {
    if (typeof rawValue === 'boolean') {
      return rawValue
    }
    throw new Error('invalid bool')
  }
  return rawValue === null ? null : String(rawValue)
}

export function normalizeFieldValueForSave (
  field: PluginSettingField,
  rawValue: unknown,
) {
  if (isNestedEditorField(field) && field.schema) {
    return normalizeBySchema(field.schema, rawValue)
  }
  if ((field.type === 'int' || field.type === 'float') && rawValue === '') {
    return null
  }
  if (field.type === 'int') {
    return normalizeScalarNumberValue('int', rawValue)
  }
  if (field.type === 'float') {
    return normalizeScalarNumberValue('float', rawValue)
  }
  if (field.type_category === 'sequence') {
    return normalizeSequenceValue(field, rawValue)
  }
  if (field.type_category === 'mapping') {
    if (typeof rawValue !== 'string' || !rawValue.trim()) {
      return null
    }
    return JSON.parse(rawValue)
  }
  if (
    field.type_category === 'path'
    || field.type_category === 'duration'
    || field.type_category === 'text_like'
  ) {
    return rawValue === null ? null : String(rawValue)
  }
  return rawValue
}

function comparableBySchema (
  schema: PluginSettingSchema,
  value: unknown,
): unknown {
  if (value == null) {
    return null
  }
  if (schema.type === 'float') {
    return Number(value)
  }
  if ((schema.type === 'list' || schema.type === 'set') && Array.isArray(value)) {
    const itemSchema = schema.item_schema?.schema
    return value.map(item => itemSchema ? comparableBySchema(itemSchema, item) : item)
  }
  if ((schema.type === 'dict' || schema.fields.length > 0) && isPlainObject(value)) {
    const entries = Object.entries(value).toSorted(([left], [right]) => left.localeCompare(right))
    if (schema.type === 'dict') {
      const valueSchema = schema.value_schema?.schema
      return Object.fromEntries(
        entries.map(([key, item]) => [key, valueSchema ? comparableBySchema(valueSchema, item) : item]),
      )
    }
    const fieldMap = new Map(schema.fields.map(field => [field.key, field.schema]))
    return Object.fromEntries(
      entries.map(([key, item]) => [key, fieldMap.has(key) ? comparableBySchema(fieldMap.get(key)!, item) : item]),
    )
  }
  return value
}

function isPlainObject (value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function normalizeComparableFieldValue (
  field: PluginSettingField,
  value: unknown,
) {
  if (value == null) {
    return null
  }
  if (field.schema) {
    return comparableBySchema(field.schema, value)
  }
  if (field.type === 'float') {
    return Number(value)
  }
  if (field.type_category === 'sequence') {
    return Array.isArray(value)
      ? value.map(item => field.item_type === 'float' ? Number(item) : item)
      : []
  }
  return value
}

export function resolveNullableFieldValue (
  field: PluginSettingField,
  value: unknown,
) {
  if (value !== null || field.allows_null) {
    return value
  }
  throw new Error('null not allowed')
}

function isSameSettingValue (left: unknown, right: unknown) {
  return JSON.stringify(left) === JSON.stringify(right)
}

export function buildSettingsUpdate (
  fields: PluginSettingField[],
  form: Record<string, unknown>,
  draftClears: Record<string, boolean>,
  invalidJsonMessage: string,
): SettingsUpdatePayload {
  const values: Record<string, unknown> = {}
  const clear: string[] = []
  for (const field of fields) {
    if (!field.editable) {
      continue
    }
    if (draftClears[field.key] && field.has_local_override) {
      clear.push(field.key)
      continue
    }
    let value = form[field.key]
    try {
      value = normalizeFieldValueForSave(field, value)
    } catch (error) {
      const message = error instanceof Error ? error.message : invalidJsonMessage
      throw new Error(`${field.key}: ${message}`)
    }
    value = resolveNullableFieldValue(field, value)
    const currentValue = normalizeComparableFieldValue(field, field.current_value)
    if (!isSameSettingValue(value, currentValue)) {
      values[field.key] = value
    }
  }
  return { values, clear }
}

export function buildSettingsPreviewItems (
  fields: PluginSettingField[],
  form: Record<string, unknown>,
  draftOverrides: Record<string, boolean>,
  draftClears: Record<string, boolean>,
  invalidJsonMessage: string,
) {
  try {
    const editableFields = fields.filter(field =>
      field.editable
      && (
        field.has_local_override
        || Boolean(draftOverrides[field.key])
        || Boolean(draftClears[field.key])
      ),
    )

    const payload = buildSettingsUpdate(
      editableFields,
      form,
      draftClears,
      invalidJsonMessage,
    )
    return editableFields
      .filter(field =>
        Object.prototype.hasOwnProperty.call(payload.values, field.key)
        || payload.clear.includes(field.key),
      )
      .map<SettingsPreviewItem>(field => ({
        key: field.key,
        current: displayFieldValue(field.current_value),
        next: displayFieldValue(
          payload.clear.includes(field.key)
            ? field.base_value
            : payload.values[field.key],
        ),
      }))
  } catch {
    return []
  }
}

export function buildRevertValues (
  fields: PluginSettingField[],
  values: Record<string, unknown>,
  clear: string[] = [],
) {
  const revertValues: Record<string, unknown> = {}
  for (const field of fields) {
    if (
      Object.prototype.hasOwnProperty.call(values, field.key)
      || clear.includes(field.key)
    ) {
      revertValues[field.key] = field.current_value
    }
  }
  return revertValues
}

export function hasPendingChanges (
  fields: PluginSettingField[],
  form: Record<string, unknown>,
  draftClears: Record<string, boolean>,
  invalidJsonMessage: string,
) {
  try {
    const payload = buildSettingsUpdate(fields, form, draftClears, invalidJsonMessage)
    return payload.clear.length > 0 || Object.keys(payload.values).length > 0
  } catch {
    return fields.length > 0
  }
}
