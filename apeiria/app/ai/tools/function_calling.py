"""Pure helpers for model function-calling integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from apeiria.app.ai.future_task.models import AIFutureTaskToolInput
from apeiria.app.ai.model.adapter import AIModelToolCall, AIModelToolDefinition
from apeiria.app.ai.tools.models import (
    AIMemoryQueryObservationInput,
    AIMemoryUpdateInput,
    AINoneBotCapabilityRequest,
    AIToolIntent,
)

if TYPE_CHECKING:
    from apeiria.app.ai.tools.models import AIToolSpec

_TOOL_NAME_MAP = {
    "future_task.manage": "future_task_manage",
    "memory.query": "memory_query",
    "memory.update": "memory_update",
    "relationship.inspect": "relationship_inspect",
    "plugin.capability": "plugin_capability",
}

_FUNCTION_NAME_MAP = {value: key for key, value in _TOOL_NAME_MAP.items()}
_DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")


def build_function_tools(
    tools: list["AIToolSpec"],
    *,
    current_time: datetime | None = None,
) -> tuple[AIModelToolDefinition, ...]:
    """Convert tool specs into function-calling definitions."""

    definitions: list[AIModelToolDefinition] = []
    for tool in tools:
        function_name = _TOOL_NAME_MAP.get(tool.name)
        if function_name is None:
            continue
        definitions.append(
            AIModelToolDefinition(
                name=function_name,
                description=_build_tool_description(
                    tool_name=tool.name,
                    description=tool.description,
                    current_time=current_time,
                ),
                parameters=_build_tool_parameters(tool.name),
            )
        )
    return tuple(definitions)


def build_intents_from_tool_calls(
    tool_calls: tuple[AIModelToolCall, ...],
) -> list[AIToolIntent]:
    """Convert model-returned tool calls into executable intents."""

    intents: list[AIToolIntent] = []
    for tool_call in tool_calls:
        intent = _build_intent_from_tool_call(tool_call)
        if intent is not None:
            intents.append(intent)
    return intents


def _build_intent_from_tool_call(
    tool_call: AIModelToolCall,
) -> AIToolIntent | None:
    tool_name = _FUNCTION_NAME_MAP.get(tool_call.name)
    if tool_name is None:
        return None
    handler = _INTENT_BUILDERS.get(tool_name)
    if handler is None:
        return None
    return handler(tool_call.arguments)


def _build_memory_update_intent(
    arguments: dict[str, Any],
) -> AIToolIntent | None:
    memory_id = _coerce_optional_string(arguments.get("memory_id"))
    updated_content = _coerce_optional_string(arguments.get("updated_content"))
    if memory_id is None or updated_content is None:
        return None
    salience = _coerce_optional_float(arguments.get("salience"))
    confidence = _coerce_optional_float(arguments.get("confidence"))
    return AIToolIntent(
        tool_name="memory.update",
        kind="update_memory",
        input_payload=AIMemoryUpdateInput(
            memory_id=memory_id,
            updated_content=updated_content,
            salience=salience,
            confidence=confidence,
        ),
        reason="model-selected function call",
    )


def _build_future_task_intent(arguments: dict[str, Any]) -> AIToolIntent | None:
    tool_input = _parse_future_task_input(arguments)
    if tool_input is None:
        return None
    return AIToolIntent(
        tool_name="future_task.manage",
        kind="manage_future_task",
        input_payload=tool_input,
        reason="model-selected function call",
    )


def _build_memory_query_intent(arguments: dict[str, Any]) -> AIToolIntent:
    return AIToolIntent(
        tool_name="memory.query",
        kind="observe_read_only",
        input_payload=AIMemoryQueryObservationInput(
            query_text=str(arguments.get("query_text", "")),
        ),
        reason="model-selected function call",
    )


def _build_relationship_inspect_intent(_arguments: dict[str, Any]) -> AIToolIntent:
    return AIToolIntent(
        tool_name="relationship.inspect",
        kind="observe_read_only",
        input_payload=None,
        reason="model-selected function call",
    )


def _build_capability_intent(arguments: dict[str, Any]) -> AIToolIntent | None:
    capability_name = arguments.get("capability_name")
    if not isinstance(capability_name, str) or not capability_name.strip():
        return None
    capability_arguments = arguments.get("arguments", {})
    if not isinstance(capability_arguments, dict):
        capability_arguments = {}
    return AIToolIntent(
        tool_name="plugin.capability",
        kind="invoke_capability",
        input_payload=AINoneBotCapabilityRequest(
            capability_name=capability_name,
            arguments=capability_arguments,
        ),
        reason="model-selected function call",
    )


_INTENT_BUILDERS: dict[str, Any] = {
    "future_task.manage": _build_future_task_intent,
    "memory.query": _build_memory_query_intent,
    "memory.update": _build_memory_update_intent,
    "relationship.inspect": _build_relationship_inspect_intent,
    "plugin.capability": _build_capability_intent,
}


def _build_tool_description(
    *,
    tool_name: str,
    description: str,
    current_time: datetime | None,
) -> str:
    if tool_name != "future_task.manage" or current_time is None:
        return description
    localized = current_time.astimezone(_DISPLAY_TIMEZONE)
    return (
        f"{description}. Current reference time: {localized.isoformat()}. "
        "Convert relative times like tomorrow morning into absolute ISO-8601 "
        "timestamps with timezone offset before calling this tool."
    )


def _build_tool_parameters(tool_name: str) -> dict[str, Any]:
    if tool_name == "future_task.manage":
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "cancel", "list"],
                    "description": (
                        "create schedules a reminder, cancel removes one by task_id, "
                        "list shows existing tasks for the current conversation."
                    ),
                },
                "title": {
                    "type": "string",
                    "description": "Short reminder title for create.",
                },
                "description": {
                    "type": "string",
                    "description": "Reminder content for create.",
                },
                "trigger_at": {
                    "type": "string",
                    "description": (
                        "Absolute ISO-8601 datetime with timezone offset for create."
                    ),
                },
                "task_id": {
                    "type": "string",
                    "description": "Existing task_id for cancel.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional max items for list, default 5.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        }
    if tool_name == "memory.query":
        return {
            "type": "object",
            "properties": {
                "query_text": {
                    "type": "string",
                    "description": (
                        "The lookup query for recalled persistent memory context."
                    ),
                }
            },
            "required": ["query_text"],
            "additionalProperties": False,
        }
    if tool_name == "memory.update":
        return {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": (
                        "One recalled memory_id from memory.query or prior tool "
                        "results in the current scene."
                    ),
                },
                "updated_content": {
                    "type": "string",
                    "description": "Replacement memory content.",
                },
                "salience": {
                    "type": "number",
                    "description": "Optional revised salience between 0 and 1.",
                },
                "confidence": {
                    "type": "number",
                    "description": "Optional revised confidence between 0 and 1.",
                },
            },
            "required": ["memory_id", "updated_content"],
            "additionalProperties": False,
        }
    if tool_name == "relationship.inspect":
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {
            "capability_name": {
                "type": "string",
                "description": "The registered capability name to invoke.",
            },
            "arguments": {
                "type": "object",
                "description": "Structured arguments for the capability.",
            },
        },
        "required": ["capability_name"],
        "additionalProperties": False,
    }


def _parse_future_task_input(arguments: dict[str, Any]) -> AIFutureTaskToolInput | None:
    action = arguments.get("action")
    if action not in {"create", "cancel", "list"}:
        return None

    trigger_at = _parse_iso_datetime(arguments.get("trigger_at"))
    limit_value = arguments.get("limit")
    limit = int(limit_value) if isinstance(limit_value, int) else None
    return AIFutureTaskToolInput(
        action=action,
        title=_coerce_optional_string(arguments.get("title")),
        description=_coerce_optional_string(arguments.get("description")),
        trigger_at=trigger_at,
        task_id=_coerce_optional_string(arguments.get("task_id")),
        limit=limit,
    )


def _coerce_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _coerce_optional_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed
