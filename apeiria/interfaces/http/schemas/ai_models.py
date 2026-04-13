"""Pydantic request/response schemas for AI admin APIs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AIPersonaItem(BaseModel):
    persona_id: str
    name: str
    description: str
    system_prompt: str
    style_prompt: str
    enabled: bool


class AIPersonaBindingItem(BaseModel):
    binding_id: str
    scope_type: str
    scope_id: str
    persona_id: str


class AIPersonaUpsertRequest(BaseModel):
    persona_id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2000)
    system_prompt: str = Field(min_length=1, max_length=20000)
    style_prompt: str = Field(default="", max_length=20000)
    enabled: bool = True


class AIMemoryItem(BaseModel):
    memory_id: str
    memory_domain: str
    memory_type: str
    subject_type: str
    subject_id: str
    content: str
    source_turn_id: str | None = None
    salience: float
    confidence: float
    last_recalled_at: str | None = None
    created_at: str


class AIRecentTargetItem(BaseModel):
    target_type: str
    subject_type: str
    subject_id: str
    title: str
    subtitle: str | None = None
    conversation_id: str | None = None
    platform: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None
    subject_user_id: str | None = None
    last_active_at: str | None = None


class AIMemoryCreateRequest(BaseModel):
    memory_domain: Literal["social", "knowledge"]
    memory_type: Literal["fact", "preference", "relationship", "note"]
    subject_type: str = Field(min_length=1, max_length=32)
    subject_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=10000)
    salience: float = Field(default=0.6, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class AIMemoryDeleteResult(BaseModel):
    deleted: bool


class AISourcePresetItem(BaseModel):
    preset_type: str
    display_name: str
    capability_type: str
    client_type: str
    default_api_base: str | None = None
    description: str


class AISourceItem(BaseModel):
    source_id: str
    name: str
    capability_type: str
    client_type: str
    preset_type: str
    api_base: str | None = None
    api_key_env_name: str | None = None
    enabled: bool
    timeout_seconds: int | None = None
    custom_headers: dict[str, str] = {}
    extra_config: dict[str, object] = {}


class AISourceUpsertRequest(BaseModel):
    source_id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    capability_type: str = Field(min_length=1, max_length=32)
    preset_type: str = Field(min_length=1, max_length=64)
    api_base: str | None = Field(default=None, max_length=2000)
    api_key_env_name: str | None = Field(default=None, max_length=128)
    enabled: bool = True
    timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    custom_headers: dict[str, str] = {}
    extra_config: dict[str, object] = {}


class AISourceModelFetchRequest(BaseModel):
    source_id: str | None = Field(default=None, max_length=64)
    preset_type: str | None = Field(default=None, max_length=64)
    api_base: str | None = Field(default=None, max_length=2000)
    api_key_env_name: str | None = Field(default=None, max_length=128)
    api_key: str | None = Field(default=None, max_length=512)


class AISourceModelTestRequest(BaseModel):
    source_id: str | None = Field(default=None, max_length=64)
    preset_type: str | None = Field(default=None, max_length=64)
    api_base: str | None = Field(default=None, max_length=2000)
    api_key_env_name: str | None = Field(default=None, max_length=128)
    api_key: str | None = Field(default=None, max_length=512)
    model_identifier: str = Field(min_length=1, max_length=256)


class AISourceModelTestResult(BaseModel):
    model_identifier: str
    content: str
    tool_call_count: int


class AIChatModelItem(BaseModel):
    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool
    is_default: bool
    extra_params: dict[str, object] = {}


class AIChatModelUpsertRequest(BaseModel):
    model_id: str | None = None
    source_id: str = Field(min_length=1, max_length=64)
    model_identifier: str = Field(min_length=1, max_length=256)
    display_name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    is_default: bool = False
    extra_params: dict[str, object] = {}


class AIConversationItem(BaseModel):
    conversation_id: str
    platform: str
    bot_id: str
    scope_type: str
    scope_id: str
    subject_user_id: str | None = None
    short_summary: str | None = None
    created_at: str
    updated_at: str
    last_active_at: str


class AIConversationTurnItem(BaseModel):
    turn_id: str
    conversation_id: str
    sender_type: str
    sender_id: str
    content_text: str
    created_at: str
    raw_payload: dict[str, object] | None = None
    trace_id: str | None = None
    source_id: str | None = None
    model_name: str | None = None
    recalled_memory_count: int | None = None
    tool_observation_count: int | None = None


class AIConversationPromptPreviewItem(BaseModel):
    conversation_id: str
    latest_user_message: str | None = None
    source_id: str | None = None
    profile_id: str | None = None
    model_name: str | None = None
    persona_id: str | None = None
    conversation_summary: str | None = None
    relationship_context: str | None = None
    tool_policy: str | None = None
    social_action: str | None = None
    social_tool_mode: str | None = None
    social_reason_text: str | None = None
    social_reason_codes: list[str] = []
    social_policy_source: str | None = None
    tool_results: list[str] = []
    memories: list[AIMemoryItem] = []
    social_memory_count: int = 0
    knowledge_memory_count: int = 0
    rendered_prompt: str


class AIFutureTaskItem(BaseModel):
    task_id: str
    conversation_id: str
    platform: str
    scope_type: str
    scope_id: str
    user_id: str | None = None
    title: str
    description: str
    trigger_at: str
    status: str
    source_turn_id: str | None = None
    scheduler_job_id: str | None = None
    last_error: str | None = None
    created_at: str
    updated_at: str


class AIRelationshipStateItem(BaseModel):
    affinity_id: str
    platform: str
    group_id: str | None = None
    user_id: str
    score: float
    mood_tags: list[str] = []
    last_event_at: str


class AIRelationshipScoreUpdateRequest(BaseModel):
    platform: str = Field(min_length=1, max_length=32)
    user_id: str = Field(min_length=1, max_length=64)
    group_id: str | None = Field(default=None, max_length=128)
    score: float = Field(ge=-1.0, le=1.0)


class AIToolItem(BaseModel):
    name: str
    description: str
    read_only: bool
    concurrency_safe: bool
    risk_level: str
    is_capability_bridge: bool = False


class AISkillItem(BaseModel):
    name: str
    description: str
    display_name: str
    display_description: str
    read_only: bool
    concurrency_safe: bool
    risk_level: str
    risk_label: str
    is_capability_bridge: bool = False


class AIToolExecutionItem(BaseModel):
    execution_id: str
    conversation_id: str
    tool_name: str
    status: str
    input_json: str | None = None
    output_json: str | None = None
    created_at: str


class AIToolPolicyPreviewRequest(BaseModel):
    scope_type: str = Field(min_length=1, max_length=32)
    is_tome: bool = False
    allow_read_only_tools: bool = True
    capability_mode: str = Field(default="off", min_length=1, max_length=32)


class AIToolIntentPreviewRequest(BaseModel):
    message_text: str = Field(min_length=1, max_length=2000)
    scope_type: str = Field(min_length=1, max_length=32)
    is_tome: bool = False
    allow_read_only_tools: bool = True
    capability_mode: str = Field(default="off", min_length=1, max_length=32)


class AIToolIntentPreviewItem(BaseModel):
    tool_name: str
    kind: str
    reason: str | None = None
    input_payload: object | None = None


class AIToolPolicyPreviewItem(BaseModel):
    execution_enabled: bool
    allowed_tool_names: list[str] | None = None
    denied_tool_names: list[str] = []
    allow_high_risk_tools: bool
    allow_capability_bridge: bool


class AIToolPolicyBindingItem(BaseModel):
    binding_id: str
    scope_type: str
    scope_id: str
    allow_read_only_tools: bool
    capability_mode: str


class AIToolPolicyBindingCreateRequest(BaseModel):
    scope_type: str = Field(min_length=1, max_length=32)
    scope_id: str = Field(min_length=1, max_length=128)
    allow_read_only_tools: bool = True
    capability_mode: str = Field(default="off", min_length=1, max_length=32)


class AIToolPolicyBindingUpdateRequest(BaseModel):
    binding_id: str = Field(min_length=1, max_length=64)
    allow_read_only_tools: bool
    capability_mode: str = Field(min_length=1, max_length=32)


class AICapabilityPreviewRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128)
    scope_type: str = Field(min_length=1, max_length=32)
    is_tome: bool = False
    allow_read_only_tools: bool = True
    capability_mode: str = Field(default="off", min_length=1, max_length=32)


class AICapabilityPreviewItem(BaseModel):
    capability_name: str
    registered: bool
    allowed: bool
    reason: str
    allow_capability_bridge: bool
    execution_enabled: bool


class AICapabilityItem(BaseModel):
    capability_name: str
    bound_tool_name: str


class AIModelProfileItem(BaseModel):
    profile_id: str
    name: str
    model_id: str
    task_class: str
    priority: int
    enabled: bool
    fallback_profile_id: str | None = None


class AIModelProfileUpsertRequest(BaseModel):
    profile_id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=64)
    task_class: str = Field(min_length=1, max_length=64)
    priority: int = Field(default=100, ge=0, le=10000)
    enabled: bool = True
    fallback_profile_id: str | None = Field(default=None, max_length=64)


class AIModelBindingItem(BaseModel):
    binding_id: str
    scope_type: str
    scope_id: str
    profile_id: str


class AIModelCatalogItem(BaseModel):
    id: str
    name: str
