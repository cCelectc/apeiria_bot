"""Pure helpers for model function-calling integration."""

from datetime import datetime
from zoneinfo import ZoneInfo

from apeiria.ai.capabilities import AICapabilityContract
from apeiria.ai.capabilities.projections import project_executable_contract
from apeiria.ai.model.runtime.adapter import AIModelToolCall, AIModelToolDefinition
from apeiria.ai.tools.models import AIToolIntent, AIToolIntentKind

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
    tools: list[AICapabilityContract],
    *,
    current_time: datetime | None = None,
) -> tuple[AIModelToolDefinition, ...]:
    """Convert executable capability contracts into function-call definitions."""

    definitions: list[AIModelToolDefinition] = []
    for contract in tools:
        definition = project_executable_contract(contract)
        definitions.append(
            _build_tool_definition_with_description(
                definition,
                tool_name=contract.name,
                description=contract.description,
                current_time=current_time,
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
    "plugin.inspect": "invoke_capability",
    "future_task.manage": "manage_future_task",
}
_DEFAULT_KIND: AIToolIntentKind = "observe_read_only"


def _infer_intent_kind(
    tool_name: str,
) -> AIToolIntentKind:
    """Infer the intent kind from the tool name."""

    return _TOOL_KIND_MAP.get(tool_name, _DEFAULT_KIND)


def _build_tool_definition_with_description(
    definition: AIModelToolDefinition,
    *,
    tool_name: str,
    description: str,
    current_time: datetime | None,
) -> AIModelToolDefinition:
    return AIModelToolDefinition(
        name=definition.name,
        description=_build_tool_description(
            tool_name=tool_name,
            description=description,
            current_time=current_time,
        ),
        parameters=definition.parameters,
    )


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
