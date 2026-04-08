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
