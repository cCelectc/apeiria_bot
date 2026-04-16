"""Pure helpers for model function-calling integration."""

from datetime import datetime
from zoneinfo import ZoneInfo

from apeiria.app.ai.model.adapter import AIModelToolCall, AIModelToolDefinition
from apeiria.app.ai.tools.models import AIToolIntent, AIToolIntentKind, AIToolSpec
from apeiria.app.ai.tools.schema import build_json_schema

_DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")


def tool_name_to_function_name(tool_name: str) -> str:
    """Convert dotted tool name to function name for model API."""
    return tool_name.replace(".", "_")


def function_name_to_tool_name(function_name: str) -> str:
    """Reverse a function name back to dotted tool name.

    Heuristic: replace the *first* underscore in each known prefix group
    with a dot.  For names registered in the registry, this is validated
    during intent construction.
    """
    # Known prefixes where the first `_` is the namespace separator.
    for prefix in (
        "future_task_",
        "memory_",
        "relationship_",
        "plugin_",
    ):
        if function_name.startswith(prefix):
            ns = prefix[:-1]  # e.g. "future_task"
            rest = function_name[len(prefix) :]
            return f"{ns}.{rest}"
    # Fallback: replace first underscore
    return function_name.replace("_", ".", 1)


def build_function_tools(
    tools: list[AIToolSpec],
    *,
    current_time: datetime | None = None,
) -> tuple[AIModelToolDefinition, ...]:
    """Convert tool specs into function-calling definitions.

    Parameters are read from ``AIToolSpec.parameters`` and converted to
    JSON Schema via :func:`build_json_schema`.
    """

    definitions: list[AIModelToolDefinition] = []
    for tool in tools:
        function_name = tool_name_to_function_name(tool.name)
        parameters = (
            build_json_schema(tool.parameters)
            if tool.parameters
            else {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        )
        definitions.append(
            AIModelToolDefinition(
                name=function_name,
                description=_build_tool_description(
                    tool_name=tool.name,
                    description=tool.description,
                    current_time=current_time,
                ),
                parameters=parameters,
            )
        )
    return tuple(definitions)


def build_intents_from_tool_calls(
    tool_calls: tuple[AIModelToolCall, ...],
) -> list[AIToolIntent]:
    """Convert model-returned tool calls into executable intents."""

    intents: list[AIToolIntent] = []
    for tool_call in tool_calls:
        tool_name = function_name_to_tool_name(tool_call.name)
        intents.append(
            AIToolIntent(
                tool_name=tool_name,
                kind=_infer_intent_kind(tool_name),
                input_payload=tool_call.arguments,
                reason="model-selected function call",
            )
        )
    return intents


_TOOL_KIND_MAP: dict[str, AIToolIntentKind] = {
    "memory.query": "observe_read_only",
    "memory.update": "update_memory",
    "relationship.inspect": "observe_read_only",
    "plugin.capability": "invoke_capability",
    "future_task.manage": "manage_future_task",
}
_DEFAULT_KIND: AIToolIntentKind = "observe_read_only"


def _infer_intent_kind(
    tool_name: str,
) -> AIToolIntentKind:
    """Infer the intent kind from the tool name."""

    return _TOOL_KIND_MAP.get(tool_name, _DEFAULT_KIND)


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
