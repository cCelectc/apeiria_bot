"""Schema models for AI tool routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from apeiria.ai.tools.projection import build_provider_name_map

if TYPE_CHECKING:
    from apeiria.ai.tools import (
        AIToolDefinition,
        AIToolExecutionView,
        AIToolIntentPreview,
        AIToolPolicy,
        AIToolPolicyBindingSpec,
    )


class AIToolItem(BaseModel):
    name: str
    description: str
    origin: str
    required_level: str
    enabled: bool
    manageable: bool
    readiness_code: str
    readiness_reason: str
    provider_name: str
    tags: list[str] = []
    version: int
    status: str = "not_evaluated"
    denied_reason: str | None = None
    unavailable_reason: str | None = None


class AIToolExecutionItem(BaseModel):
    execution_id: str
    session_id: str
    tool_name: str
    status: str
    reason: str | None = None
    trace_id: str | None = None
    call_id: str | None = None
    input_json: str | None = None
    output_json: str | None = None
    created_at: str


class AIToolPolicyPreviewRequest(BaseModel):
    scope_type: str = Field(min_length=1, max_length=32)
    is_tome: bool = False
    allowed_level: str = Field(default="none", min_length=1, max_length=16)


class AIToolIntentPreviewRequest(BaseModel):
    message_text: str = Field(min_length=1, max_length=2000)
    scope_type: str = Field(min_length=1, max_length=32)
    is_tome: bool = False
    allowed_level: str = Field(default="none", min_length=1, max_length=16)


class AIToolIntentPreviewItem(BaseModel):
    tool_name: str
    kind: str
    reason: str | None = None
    input_payload: object | None = None


class AIToolPolicyPreviewItem(BaseModel):
    allowed_level: str


class AIToolPolicyBindingItem(BaseModel):
    binding_id: str
    scope_type: str
    scope_id: str
    allowed_level: str


class AIToolPolicyBindingCreateRequest(BaseModel):
    scope_type: str = Field(min_length=1, max_length=32)
    scope_id: str = Field(min_length=1, max_length=128)
    allowed_level: str = Field(default="none", min_length=1, max_length=16)


class AIToolPolicyBindingUpdateRequest(BaseModel):
    binding_id: str = Field(min_length=1, max_length=64)
    allowed_level: str = Field(min_length=1, max_length=16)


def to_ai_tool_item(
    item: "AIToolDefinition",
    *,
    status: str = "not_evaluated",
    denied_reason: str | None = None,
    unavailable_reason: str | None = None,
) -> AIToolItem:
    name_map = build_provider_name_map((item,))
    provider_name = next(iter(name_map))
    return AIToolItem(
        name=item.name,
        description=item.description,
        origin=item.origin,
        required_level=item.required_level.value,
        enabled=item.enabled,
        manageable=item.manageable,
        readiness_code=item.readiness.code,
        readiness_reason=item.readiness.reason,
        provider_name=provider_name,
        tags=list(item.tags),
        version=item.version,
        status=status,
        denied_reason=denied_reason,
        unavailable_reason=unavailable_reason,
    )


def to_ai_tool_execution_item(item: "AIToolExecutionView") -> AIToolExecutionItem:
    return AIToolExecutionItem(
        execution_id=item.execution_id,
        session_id=item.session_id,
        tool_name=item.tool_name,
        status=item.status,
        reason=item.reason,
        trace_id=item.trace_id,
        call_id=item.call_id,
        input_json=item.input_json,
        output_json=item.output_json,
        created_at=item.created_at.isoformat(),
    )


def to_ai_tool_intent_preview_item(
    item: "AIToolIntentPreview",
) -> AIToolIntentPreviewItem:
    return AIToolIntentPreviewItem(
        tool_name=item.tool_name,
        kind=item.kind,
        reason=item.reason,
        input_payload=item.input_payload,
    )


def to_ai_tool_policy_preview_item(item: "AIToolPolicy") -> AIToolPolicyPreviewItem:
    return AIToolPolicyPreviewItem(allowed_level=item.allowed_level.value)


def to_ai_tool_policy_binding_item(
    item: "AIToolPolicyBindingSpec",
) -> AIToolPolicyBindingItem:
    return AIToolPolicyBindingItem(
        binding_id=item.binding_id,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        allowed_level=item.allowed_level.value,
    )
