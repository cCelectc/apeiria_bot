export interface AIToolItem {
  name: string
  description: string
  display_name?: string
  display_description?: string
  read_only: boolean
  concurrency_safe: boolean
  risk_level: string
  risk_label?: string
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
  session_id: string
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
  allow_host_actions: boolean
}

export interface AICapabilityItem {
  capability_name: string
  kind: string
  origin: string
  description: string
  read_only: boolean
  concurrency_safe: boolean
  risk_level: string
  risk_label: string
  availability: string
  binding_key: string | null
  binding_type: string | null
  policy_status: string
  diagnostics: string[]
  required_capabilities: string[]
  tags: string[]
  version: number
}

export interface AICapabilityPreviewItem {
  capability_name: string
  registered: boolean
  allowed: boolean
  reason: string
  allow_host_actions: boolean
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
  anchor_type: string
  anchor_id: string
  memory_layer: string
  memory_kind: string
  content: string
  is_editable: boolean
  is_ignored: boolean
  source_message_id: string | null
  salience: number
  confidence: number
  last_recalled_at: string | null
  created_at: string
}

export interface AIRecentTargetItem {
  target_type: string
  anchor_type: string
  anchor_id: string
  title: string
  subtitle: string | null
  scene_id: string | null
  platform: string | null
  scope_type: string | null
  scope_id: string | null
  user_id: string | null
  last_active_at: string | null
}

export interface AIMemoryCreateRequest {
  memory_layer: string
  memory_kind: string
  anchor_type: string
  anchor_id: string
  content: string
  salience?: number
  confidence?: number
}

export interface AIKnowledgeStateItem {
  rag_enabled: boolean
  document_count: number
  chunk_count: number
}

export interface AIKnowledgeDocumentItem {
  document_id: string
  title: string
  source_file_name: string
  content_hash: string
  status: string
  chunk_count: number
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface AIKnowledgeChunkItem {
  chunk_id: string
  document_id: string
  ordinal: number
  chunk_hash: string
  text: string
  char_count: number
  embedding_model: string | null
  embedding_status: string
  created_at: string
  updated_at: string
}

export interface AIKnowledgeRebuildDiagnosticsItem {
  processed_count: number
  skipped_count: number
  failed_count: number
  stale_cleanup_count: number
}

export interface AIKnowledgeUploadResultItem {
  document: AIKnowledgeDocumentItem
  chunks: AIKnowledgeChunkItem[]
  diagnostics: AIKnowledgeRebuildDiagnosticsItem
}

export interface AIKnowledgeRetrievalItem {
  label: string
  document_id: string
  chunk_id: string
  title: string
  source_file_name: string
  rank: number
  score: number
  rerank_score: number | null
  excerpt: string
}

export interface AIKnowledgeRetrievalDiagnosticsItem {
  candidate_count: number
  selected_count: number
  missing_embedding_count: number
  stale_embedding_count: number
  rerank_status: string
  degradation_reason: string | null
}

export interface AIKnowledgeRetrievalResultItem {
  items: AIKnowledgeRetrievalItem[]
  diagnostics: AIKnowledgeRetrievalDiagnosticsItem
}

export interface AISourcePresetItem {
  preset_type: string
  display_name: string
  capability_type: string
  client_type: string
  adapter_kind: string
  default_api_base: string | null
  description: string
  capability_metadata: Record<string, unknown>
  default_options: Record<string, unknown>
  capability_provenance: Record<string, unknown>
}

export interface AIBootstrapResponse {
  source_presets: AISourcePresetItem[]
  scope_types: string[]
  capability_modes: string[]
  task_classes: string[]
}

export interface AISourceItem {
  source_id: string
  name: string
  capability_type: string
  client_type: string
  adapter_kind: string | null
  preset_type: string
  api_base: string | null
  enabled: boolean
  timeout_seconds: number | null
  custom_headers: Record<string, string>
  extra_config: Record<string, unknown>
  capability_metadata: Record<string, unknown>
  default_options: Record<string, unknown>
  capability_provenance: Record<string, unknown>
}

export interface AISourceModelItem {
  model_id: string
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
  extra_params: Record<string, unknown>
  capability_metadata: Record<string, unknown>
  default_options: Record<string, unknown>
  capability_provenance: Record<string, unknown>
}

export interface AISourceModelTestResult {
  model_identifier: string
  content: string
  tool_call_count: number
}

export interface AISessionItem {
  session_id: string
  platform: string
  bot_id: string
  scene_type: string
  scene_id: string
  subject_id: string | null
  summary_text: string | null
  created_at: string
  updated_at: string
  last_message_at: string
}

export interface AIChatMessageItem {
  message_id: string
  session_id: string
  author_role: string
  author_id: string
  author_name: string | null
  text_content: string
  content: Record<string, unknown> | null
  meta: Record<string, unknown> | null
  raw_data: Record<string, unknown> | null
  created_at: string
  trace_id: string | null
  source_id: string | null
  model_name: string | null
  recalled_memory_count: number | null
  tool_observation_count: number | null
}

export interface AISessionPromptChannelsItem {
  mode: string
  system_instructions: string[]
  persona: string
  style: string | null
  relationship: string | null
  person_profile: string[]
  social_policy: string | null
  tool_policy: string | null
  future_task: string | null
  tool_results: string[]
  operator_memories: string[]
  summary_memories: string[]
  long_term_memories: string[]
  knowledge_memories: string[]
  conversation_summary: string | null
  context_priority: string[]
  conversation_messages: string[]
  response_rules: string[]
  instruction: string
  sections: AISessionPromptSectionItem[]
}

export interface AISessionPromptSectionItem {
  role: string
  name: string
  content: string
}

export interface AISessionPromptDiagnosticsItem {
  prompt_purpose: string
  stable_section_names: string[]
  dynamic_section_names: string[]
  stable_section_count: number
  dynamic_section_count: number
  total_section_count: number
}

export interface AISessionPromptPreviewItem {
  session_id: string
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
  hard_rule_action: string | null
  hard_rule_reason_text: string | null
  hard_rule_reason_codes: string[]
  social_action: string | null
  social_tool_mode: string | null
  social_reason_text: string | null
  social_reason_codes: string[]
  social_policy_source: string | null
  preview_diagnostics: string[]
  tool_results: string[]
  memories: AIMemoryItem[]
  operator_memory_count: number
  summary_memory_count: number
  long_term_memory_count: number
  knowledge_memory_count: number
  planning_prompt_diagnostics: AISessionPromptDiagnosticsItem
  roleplay_prompt_diagnostics: AISessionPromptDiagnosticsItem | null
  planning_channels: AISessionPromptChannelsItem
  roleplay_channels: AISessionPromptChannelsItem | null
  rendered_roleplay_prompt: string | null
  rendered_prompt: string
}

export interface AIFutureTaskItem {
  task_id: string
  session_id: string
  platform: string
  scene_type: string
  scene_id: string
  user_id: string | null
  title: string
  description: string
  trigger_at: string
  status: string
  source_message_id: string | null
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
  last_event_at: string | null
  last_decay_at: string | null
  projected_tone: string
  warmth_bias: number
  initiative_bias: number
  style_modulation: string[]
  effective_score: number
  effective_mood_tags: string[]
  effective_projected_tone: string
  effective_warmth_bias: number
  effective_initiative_bias: number
  effective_style_modulation: string[]
}

export interface AIRelationshipEventItem {
  event_id: string
  affinity_id: string
  platform: string
  group_id: string | null
  user_id: string
  event_type: string
  score_delta: number
  score_after: number
  mood_tag: string | null
  reason: string | null
  created_at: string
}

export interface AIModelCatalogItem {
  id: string
  name: string
  capability_metadata: Record<string, unknown>
  default_options: Record<string, unknown>
  capability_provenance: Record<string, unknown>
}

export interface AIPersonMemoryPointItem {
  category: string
  content: string
  confidence: number
  source_message_id: string | null
}

export interface AIPersonProfileItem {
  person_id: string
  platform: string
  user_id: string
  person_name: string | null
  nickname: string | null
  name_reason: string | null
  memory_points: AIPersonMemoryPointItem[]
  is_known: boolean
  know_since: string | null
  last_interaction: string
  created_at: string
  updated_at: string
}

export interface AIMemoryBulkActionResult {
  affected: number
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
