"""Pydantic request/response schemas for AI admin APIs."""

from __future__ import annotations

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


class AIMemoryItem(BaseModel):
    memory_id: str
    memory_type: str
    subject_type: str
    subject_id: str
    content: str
    source_turn_id: str | None = None
    salience: float
    confidence: float
    last_recalled_at: str | None = None
    created_at: str


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


class AIToolPolicyPreviewItem(BaseModel):
    execution_enabled: bool
    allowed_tool_names: list[str] | None = None
    denied_tool_names: list[str] = []
    allow_high_risk_tools: bool
    allow_capability_bridge: bool


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


class AICapabilityItem(BaseModel):
    capability_name: str
    bound_tool_name: str


class AIModelProfileItem(BaseModel):
    profile_id: str
    name: str
    provider_id: str
    model_name: str
    task_class: str
    priority: int
    enabled: bool
    fallback_profile_id: str | None = None


class AIModelBindingItem(BaseModel):
    binding_id: str
    scope_type: str
    scope_id: str
    profile_id: str


class AIProviderItem(BaseModel):
    provider_id: str
    name: str
    provider_type: str
    api_base: str | None = None
    api_key_env_name: str | None = None
    enabled: bool
    default_model: str | None = None


class AIProviderModelListRequest(BaseModel):
    provider_id: str = Field(min_length=1, max_length=64)
    api_key: str = Field(min_length=1, max_length=512)


class AIProviderModelItem(BaseModel):
    id: str
    name: str
