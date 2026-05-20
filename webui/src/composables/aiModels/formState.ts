import type { AISourceApiKeyAction, AISourceApiKeyMetadata, AISourceItem } from '@/api/ai'

export interface SourceFormState {
  source_id: string
  name: string
  preset_type: string
  capability_type: string
  adapter_kind: string
  api_base: string
  api_keys: string[]
  api_key_action: AISourceApiKeyAction
  api_key_metadata: AISourceApiKeyMetadata[]
  proxy: string
  enabled: boolean
  timeout_seconds: number | null
  embedding_dimensions: number | null
  stt_language: string
  tts_voice: string
  tts_response_format: string
  rerank_api_suffix: string
  rerank_top_n: number | null
  capability_metadata_json: string
  default_options_json: string
  capability_provenance_json: string
}

export interface ModelFormState {
  model_id: string
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
  capability_metadata_json: string
  default_options_json: string
  capability_provenance_json: string
}

export interface ProfileFormState {
  profile_id: string
  name: string
  model_id: string
  task_class: string
  priority: number
  enabled: boolean
  fallback_profile_id: string
}

export function buildSourceSnapshot(form: SourceFormState) {
  return JSON.stringify({
    adapter_kind: form.adapter_kind.trim(),
    api_base: form.api_base.trim(),
    api_key_action: form.api_key_action,
    api_keys: form.api_key_action === 'replace'
      ? normalizeApiKeys(form.api_keys)
      : [],
    capability_metadata_json: form.capability_metadata_json.trim(),
    capability_provenance_json: form.capability_provenance_json.trim(),
    capability_type: form.capability_type,
    default_options_json: form.default_options_json.trim(),
    embedding_dimensions: form.embedding_dimensions,
    enabled: form.enabled,
    name: form.name.trim(),
    preset_type: form.preset_type,
    proxy: form.proxy.trim(),
    rerank_api_suffix: form.rerank_api_suffix.trim(),
    rerank_top_n: form.rerank_top_n,
    source_id: form.source_id,
    stt_language: form.stt_language.trim(),
    timeout_seconds: form.timeout_seconds,
    tts_response_format: form.tts_response_format.trim(),
    tts_voice: form.tts_voice.trim(),
  })
}

export function buildModelSnapshot(form: ModelFormState) {
  return JSON.stringify({
    capability_metadata_json: form.capability_metadata_json.trim(),
    capability_provenance_json: form.capability_provenance_json.trim(),
    default_options_json: form.default_options_json.trim(),
    display_name: form.display_name.trim(),
    enabled: form.enabled,
    is_default: form.is_default,
    model_id: form.model_id,
    model_identifier: form.model_identifier.trim(),
    source_id: form.source_id,
  })
}

export function buildProfileSnapshot(form: ProfileFormState) {
  return JSON.stringify({
    enabled: form.enabled,
    fallback_profile_id: form.fallback_profile_id,
    model_id: form.model_id,
    name: form.name.trim(),
    priority: form.priority,
    profile_id: form.profile_id,
    task_class: form.task_class,
  })
}

export function resolveSourceCapabilityType(tab: string) {
  if (tab === 'embedding') {
    return 'embedding'
  }
  if (tab === 'stt') {
    return 'speech_to_text'
  }
  if (tab === 'tts') {
    return 'text_to_speech'
  }
  if (tab === 'rerank') {
    return 'rerank'
  }
  return 'chat_completion'
}

export function normalizeApiKeys(values: string[]) {
  return values
    .map(value => value.trim())
    .filter(Boolean)
}

export function buildSourceExtraConfig(form: SourceFormState) {
  const extraConfig: Record<string, unknown> = {}
  if (form.capability_type === 'embedding' && form.embedding_dimensions) {
    extraConfig.embedding_dimensions = form.embedding_dimensions
  }
  if (form.proxy.trim()) {
    extraConfig.proxy = form.proxy.trim()
  }
  if (form.capability_type === 'speech_to_text' && form.stt_language.trim()) {
    extraConfig.stt_language = form.stt_language.trim()
  }
  if (form.capability_type === 'text_to_speech') {
    if (form.tts_voice.trim()) {
      extraConfig.tts_voice = form.tts_voice.trim()
    }
    if (form.tts_response_format.trim()) {
      extraConfig.tts_response_format = form.tts_response_format.trim()
    }
  }
  if (form.capability_type === 'rerank') {
    if (form.rerank_api_suffix.trim()) {
      extraConfig.rerank_api_suffix = form.rerank_api_suffix.trim()
    }
    if (typeof form.rerank_top_n === 'number' && form.rerank_top_n > 0) {
      extraConfig.rerank_top_n = form.rerank_top_n
    }
  }
  return extraConfig
}

export function extractOptionalString(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

export function extractOptionalInt(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number.parseInt(value.trim(), 10)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
}

export function extractSourceApiKeys(item: AISourceItem) {
  void item
  return []
}

export function stringifyJsonObject(value: unknown) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return '{}'
  }
  return JSON.stringify(value, null, 2)
}

export function parseJsonObject(value: string) {
  const normalized = value.trim()
  if (!normalized) {
    return {}
  }
  try {
    const parsed = JSON.parse(normalized)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : {}
  } catch {
    return {}
  }
}
