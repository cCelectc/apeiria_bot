"""Schema models for AI tool routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from apeiria.ai.tools.projection import build_provider_name_map

if TYPE_CHECKING:
    from apeiria.ai.tools import (
        AIToolDefinition,
        AIToolExecutionView,
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


__all__ = [
    "AIToolExecutionItem",
    "AIToolItem",
    "to_ai_tool_execution_item",
    "to_ai_tool_item",
]
