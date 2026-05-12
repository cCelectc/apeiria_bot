import client from './client'

export interface AISourcePresetItem {
  preset_type: string
  display_name: string
  capability_type: string
  client_type: string
  adapter_kind: string
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

export interface AIModelCatalogItem {
  id: string
  name: string
  capability_metadata: Record<string, unknown>
  default_options: Record<string, unknown>
  capability_provenance: Record<string, unknown>
}

export interface AISourceModelTestResult {
  model_identifier: string
  content: string
  tool_call_count: number
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

export interface AIManagedSessionPersonaItem {
  persona_id: string
  name: string
  enabled: boolean
}

export interface AIManagedSessionItem {
  session_id: string
  platform_id: string
  platform_type: string
  message_type: string
  subject_id: string
  source_labels: Record<string, string>
  ai_enabled: boolean
  persona: AIManagedSessionPersonaItem | null
  last_observed_at: string | null
  last_message_at: string | null
  message_count: number
  diagnostic_count: number
}

export interface AIManagedSessionMessageItem {
  message_id: string
  author_role: string
  author_id: string
  text_content: string
  created_at: string
  before_reset_boundary: boolean
  trace_id: string | null
  model_name: string | null
}

export interface AIManagedSessionTraceItem {
  trace_id: string
  terminal_status: string
  skip_reason: string | null
  created_at: string
}

export interface AIManagedSessionDetailItem {
  session_id: string
  platform_id: string
  platform_type: string
  message_type: string
  subject_id: string
  source_labels: Record<string, string>
  ai_enabled: boolean
  persona: AIManagedSessionPersonaItem | null
  recent_messages: AIManagedSessionMessageItem[]
  reset_boundary_at: string | null
  prompt_preview_session_id: string
  trace_entries: AIManagedSessionTraceItem[]
  model_summary: Record<string, string | null>
  strategy_summary: Record<string, string | null>
  tool_summary: Record<string, number>
  diagnostics: Record<string, string | null>
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

export interface AIMemoryCreateRequest {
  memory_layer: string
  memory_kind: string
  anchor_type: string
  anchor_id: string
  content: string
  salience?: number
  confidence?: number
}

export interface AIMemoryBulkActionResult {
  affected: number
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

export interface AIToolItem {
  name: string
  description: string
  display_name?: string
  display_description?: string
  read_only: boolean
  mutates_state: boolean
  concurrency_safe: boolean
  risk_level: string
  risk_label?: string
  timeout_seconds: number | null
  requires_operator_approval: boolean
}

export type AISkillItem = AIToolItem

export interface AICapabilityItem {
  capability_name: string
  kind: string
  origin: string
  description: string
  read_only: boolean
  mutates_state: boolean
  concurrency_safe: boolean
  risk_level: string
  risk_label: string
  timeout_seconds: number | null
  requires_operator_approval: boolean
  availability: string
  binding_key: string | null
  binding_type: string | null
  policy_status: string
  diagnostics: string[]
  required_capabilities: string[]
  tags: string[]
  version: number
}

export interface AIToolPolicyBindingItem {
  binding_id: string
  scope_type: string
  scope_id: string
  allow_read_only_tools: boolean
  capability_mode: string
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

export interface AICapabilityPreviewItem {
  capability_name: string
  registered: boolean
  allowed: boolean
  reason: string
  allow_host_actions: boolean
  execution_enabled: boolean
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
  turn_disposition: string
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

export interface AITurnTraceItem {
  trace_id: string
  session_id: string
  runtime_mode: string
  terminal_status: string
  strategy_action: string
  strategy_reason_codes: string[]
  model_attempt_count: number
  tool_attempt_count: number
  final_response_source: string | null
  skip_reason: string | null
  delivery_status: string | null
  commit_status: string | null
  diagnostics: Record<string, unknown>
  created_at: string
}

export function getAIBootstrap() {
  return client.get<AIBootstrapResponse>('/ai/bootstrap')
}

export function getAISources() {
  return client.get<AISourceItem[]>('/ai/sources')
}

export function getAISourcePresets() {
  return client.get<AISourcePresetItem[]>('/ai/source-presets')
}

export function createAISource(payload: {
  name: string
  capability_type: string
  preset_type: string
  api_base?: string | null
  enabled: boolean
  timeout_seconds?: number | null
  custom_headers?: Record<string, string>
  extra_config?: Record<string, unknown>
  adapter_kind?: string | null
  capability_metadata?: Record<string, unknown>
  default_options?: Record<string, unknown>
  capability_provenance?: Record<string, unknown>
}) {
  return client.post<AISourceItem>('/ai/sources', payload)
}

export function updateAISource(payload: {
  source_id: string
  name: string
  capability_type: string
  preset_type: string
  api_base?: string | null
  enabled: boolean
  timeout_seconds?: number | null
  custom_headers?: Record<string, string>
  extra_config?: Record<string, unknown>
  adapter_kind?: string | null
  capability_metadata?: Record<string, unknown>
  default_options?: Record<string, unknown>
  capability_provenance?: Record<string, unknown>
}) {
  return client.put<AISourceItem | null>('/ai/sources', payload)
}

export function deleteAISource(sourceId: string) {
  return client.delete<boolean>('/ai/sources', {
    params: { source_id: sourceId },
  })
}

export function getAISourceModels(sourceId: string) {
  return client.get<AISourceModelItem[]>('/ai/sources/models', {
    params: { source_id: sourceId },
  })
}

export function fetchAISourceModels(payload: {
  source_id?: string | null
  preset_type?: string | null
  api_base?: string | null
  api_key?: string | null
  extra_config?: Record<string, unknown>
}) {
  return client.post<AIModelCatalogItem[]>('/ai/sources/models/fetch', payload)
}

export function testAISourceModel(payload: {
  source_id?: string | null
  preset_type?: string | null
  api_base?: string | null
  api_key?: string | null
  extra_config?: Record<string, unknown>
  model_identifier: string
}) {
  return client.post<AISourceModelTestResult>('/ai/sources/models/test', payload)
}

export function createAISourceModel(payload: {
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
  extra_params?: Record<string, unknown>
  capability_metadata?: Record<string, unknown>
  default_options?: Record<string, unknown>
  capability_provenance?: Record<string, unknown>
}) {
  return client.post<AISourceModelItem>('/ai/sources/models', payload)
}

export function updateAISourceModel(payload: {
  model_id: string
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
  extra_params?: Record<string, unknown>
  capability_metadata?: Record<string, unknown>
  default_options?: Record<string, unknown>
  capability_provenance?: Record<string, unknown>
}) {
  return client.put<AISourceModelItem | null>('/ai/sources/models', payload)
}

export function deleteAISourceModel(modelId: string, sourceId?: string) {
  return client.delete<boolean>('/ai/sources/models', {
    params: {
      model_id: modelId,
      source_id: sourceId,
    },
  })
}

export function getAIModelProfiles() {
  return client.get<AIModelProfileItem[]>('/ai/model-profiles')
}

export function upsertAIModelProfile(payload: {
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

export function getAIModelBindings() {
  return client.get<AIModelBindingItem[]>('/ai/model-bindings')
}

export function getAIPersonas() {
  return client.get<AIPersonaItem[]>('/ai/personas')
}

export function upsertAIPersona(payload: {
  persona_id?: string | null
  name: string
  description: string
  system_prompt: string
  style_prompt: string
  enabled: boolean
}) {
  return client.put<AIPersonaItem | null>('/ai/personas', payload)
}

export function getAIPersonaBindings() {
  return client.get<AIPersonaBindingItem[]>('/ai/persona-bindings')
}

export function getAIManagedSessions(params?: { limit?: number }) {
  return client.get<AIManagedSessionItem[]>('/ai/managed-sessions', { params })
}

export function getAIManagedSession(
  sessionId: string,
  params?: { message_limit?: number },
) {
  return client.get<AIManagedSessionDetailItem>(
    `/ai/managed-sessions/${encodeURIComponent(sessionId)}`,
    { params },
  )
}

export function updateAIManagedSessionEnabled(
  sessionId: string,
  aiEnabled: boolean,
) {
  return client.patch<AIManagedSessionDetailItem>(
    `/ai/managed-sessions/${encodeURIComponent(sessionId)}/ai-enabled`,
    { ai_enabled: aiEnabled },
  )
}

export function updateAIManagedSessionPersona(
  sessionId: string,
  personaId: string | null,
) {
  return client.patch<AIManagedSessionDetailItem>(
    `/ai/managed-sessions/${encodeURIComponent(sessionId)}/persona`,
    { persona_id: personaId },
  )
}

export function resetAIManagedSessionContext(sessionId: string) {
  return client.post<AIManagedSessionDetailItem>(
    `/ai/managed-sessions/${encodeURIComponent(sessionId)}/context-reset`,
  )
}

export function getAIRecentTargets(params?: { limit?: number }) {
  return client.get<AIRecentTargetItem[]>('/ai/recent-targets', { params })
}

export function getAIMemories(params: {
  anchor_type: string
  anchor_id: string
  memory_layer?: string
  memory_kind?: string
  query?: string
  limit?: number
}) {
  return client.get<AIMemoryItem[]>('/ai/memories', { params })
}

export function createAIMemory(payload: AIMemoryCreateRequest) {
  return client.post<AIMemoryItem>('/ai/memories', payload)
}

export function updateAIMemory(payload: {
  memory_id: string
  content: string
  salience: number
  confidence: number
}) {
  return client.patch<AIMemoryItem | null>('/ai/memories', payload)
}

export function deleteAIMemory(memoryId: string) {
  return client.delete<{ deleted: boolean }>('/ai/memories', {
    params: { memory_id: memoryId },
  })
}

export function toggleAIMemoryIgnored(memoryId: string) {
  return client.patch<AIMemoryItem | null>('/ai/memories/toggle-ignored', {
    memory_id: memoryId,
  })
}

export function bulkDeleteAIMemories(memoryIds: string[]) {
  return client.post<AIMemoryBulkActionResult>('/ai/memories/bulk-delete', {
    memory_ids: memoryIds,
  })
}

export function bulkToggleAIMemoryIgnored(memoryIds: string[], ignored: boolean) {
  return client.post<AIMemoryBulkActionResult>(
    '/ai/memories/bulk-toggle-ignored',
    { ignored, memory_ids: memoryIds },
  )
}

export function getAIPersonProfiles(params?: { limit?: number }) {
  return client.get<AIPersonProfileItem[]>('/ai/person-profiles', { params })
}

export function updateAIPersonProfile(payload: {
  person_id: string
  person_name?: string | null
  nickname?: string | null
  memory_points?: AIPersonMemoryPointItem[] | null
}) {
  return client.patch<AIPersonProfileItem | null>('/ai/person-profiles', payload)
}

export function deleteAIPersonProfile(personId: string) {
  return client.delete<boolean>('/ai/person-profiles', {
    params: { person_id: personId },
  })
}

export function getAIRelationshipStates(params?: { limit?: number }) {
  return client.get<AIRelationshipStateItem[]>('/ai/relationships/list', {
    params,
  })
}

export function updateAIRelationshipScore(payload: {
  platform: string
  user_id: string
  group_id?: string | null
  score: number
}) {
  return client.patch<AIRelationshipStateItem>('/ai/relationships', payload)
}

export function getAIRelationshipEvents(params: {
  platform: string
  user_id: string
  group_id?: string
  limit?: number
}) {
  return client.get<AIRelationshipEventItem[]>('/ai/relationships/events', {
    params,
  })
}

export function getAIKnowledgeState() {
  return client.get<AIKnowledgeStateItem>('/ai/knowledge/state')
}

export function updateAIKnowledgeState(ragEnabled: boolean) {
  return client.patch<AIKnowledgeStateItem>('/ai/knowledge/state', {
    rag_enabled: ragEnabled,
  })
}

export function uploadAIKnowledgeDocument(payload: {
  source_file_name: string
  content: string
}) {
  return client.post<AIKnowledgeUploadResultItem>('/ai/knowledge/documents', payload)
}

export function getAIKnowledgeDocuments() {
  return client.get<AIKnowledgeDocumentItem[]>('/ai/knowledge/documents')
}

export function getAIKnowledgeChunks(documentId: string) {
  return client.get<AIKnowledgeChunkItem[]>(
    `/ai/knowledge/documents/${documentId}/chunks`,
  )
}

export function rebuildAIKnowledgeDocument(documentId: string) {
  return client.post<AIKnowledgeRebuildDiagnosticsItem>(
    `/ai/knowledge/documents/${documentId}/rebuild`,
  )
}

export function deleteAIKnowledgeDocument(documentId: string) {
  return client.delete<{ deleted: boolean }>(
    `/ai/knowledge/documents/${documentId}`,
  )
}

export function previewAIKnowledgeRetrieval(payload: {
  query_text: string
  limit: number
}) {
  return client.post<AIKnowledgeRetrievalResultItem>(
    '/ai/knowledge/retrieval/preview',
    payload,
  )
}

export function getAISkills() {
  return client.get<AISkillItem[]>('/ai/skills')
}

export function getAITools() {
  return client.get<AIToolItem[]>('/ai/tools')
}

export function getAICapabilities() {
  return client.get<AICapabilityItem[]>('/ai/tools/capabilities')
}

export function getAIToolPolicyBindings() {
  return client.get<AIToolPolicyBindingItem[]>('/ai/tools/policy-bindings')
}

export function createAIToolPolicyBinding(payload: {
  scope_type: string
  scope_id: string
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolPolicyBindingItem>(
    '/ai/tools/policy-bindings',
    payload,
  )
}

export function updateAIToolPolicyBinding(payload: {
  binding_id: string
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.patch<AIToolPolicyBindingItem | null>(
    '/ai/tools/policy-bindings',
    payload,
  )
}

export function deleteAIToolPolicyBinding(bindingId: string) {
  return client.delete<{ deleted: boolean }>('/ai/tools/policy-bindings', {
    params: { binding_id: bindingId },
  })
}

export function previewAIToolPolicy(payload: {
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolPolicyPreviewItem>(
    '/ai/tools/policy-preview',
    payload,
  )
}

export function previewAIToolIntents(payload: {
  message_text: string
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolIntentPreviewItem[]>(
    '/ai/tools/intent-preview',
    payload,
  )
}

export function previewAICapability(payload: {
  capability_name: string
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AICapabilityPreviewItem>(
    '/ai/tools/capability-preview',
    payload,
  )
}

export function getAIToolExecutions(params: { scene_id: string }) {
  return client.get<AIToolExecutionItem[]>('/ai/tools/executions', { params })
}

export function getAIFutureTasks(params?: { limit?: number }) {
  return client.get<AIFutureTaskItem[]>('/ai/future-tasks', { params })
}

export function cancelAIFutureTask(taskId: string) {
  return client.delete<AIFutureTaskItem | null>('/ai/future-tasks', {
    params: { task_id: taskId },
  })
}

export function getAIScenes(params?: { limit?: number }) {
  return client.get<AISessionItem[]>('/ai/scenes', { params })
}

export function getAISceneTurns(params: { scene_id: string, limit?: number }) {
  return client.get<AIChatMessageItem[]>('/ai/scenes/turns', { params })
}

export function getAIScenePromptPreview(params: {
  scene_id: string
  turn_limit?: number
}) {
  return client.get<AISessionPromptPreviewItem | null>(
    '/ai/scenes/prompt-preview',
    { params },
  )
}

export function getAITurnTraces(params?: {
  limit?: number
  trace_id?: string
  session_id?: string
  runtime_mode?: string
  terminal_status?: string
  commit_status?: string
}) {
  return client.get<AITurnTraceItem[]>('/ai/traces', { params })
}
