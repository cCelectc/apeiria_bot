"""Pure helpers for provider function-calling integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.app.ai.model.provider import AIModelToolCall, AIModelToolDefinition
from apeiria.app.ai.tools.models import (
    AIMemoryQueryObservationInput,
    AINoneBotCapabilityRequest,
    AIToolIntent,
)

if TYPE_CHECKING:
    from apeiria.app.ai.tools.models import AIToolSpec

_TOOL_NAME_MAP = {
    "memory.query": "memory_query",
    "relationship.inspect": "relationship_inspect",
    "plugin.capability": "plugin_capability",
}

_FUNCTION_NAME_MAP = {value: key for key, value in _TOOL_NAME_MAP.items()}


def build_function_tools(
    tools: list["AIToolSpec"],
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
                description=tool.description,
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
        tool_name = _FUNCTION_NAME_MAP.get(tool_call.name)
        if tool_name is None:
            continue
        if tool_name == "memory.query":
            intents.append(
                AIToolIntent(
                    tool_name=tool_name,
                    kind="observe_read_only",
                    input_payload=AIMemoryQueryObservationInput(
                        query_text=str(tool_call.arguments.get("query_text", "")),
                    ),
                    reason="model-selected function call",
                )
            )
        elif tool_name == "relationship.inspect":
            intents.append(
                AIToolIntent(
                    tool_name=tool_name,
                    kind="observe_read_only",
                    input_payload=None,
                    reason="model-selected function call",
                )
            )
        elif tool_name == "plugin.capability":
            capability_name = tool_call.arguments.get("capability_name")
            if not isinstance(capability_name, str) or not capability_name.strip():
                continue
            arguments = tool_call.arguments.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            intents.append(
                AIToolIntent(
                    tool_name=tool_name,
                    kind="invoke_capability",
                    input_payload=AINoneBotCapabilityRequest(
                        capability_name=capability_name,
                        arguments=arguments,
                    ),
                    reason="model-selected function call",
                )
            )
    return intents


def _build_tool_parameters(tool_name: str) -> dict[str, Any]:
    if tool_name == "memory.query":
        return {
            "type": "object",
            "properties": {
                "query_text": {
                    "type": "string",
                    "description": "The memory lookup query for recalled context.",
                }
            },
            "required": ["query_text"],
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
