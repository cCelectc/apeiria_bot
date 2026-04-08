"""Pure helpers for selecting low-risk tools from user messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from apeiria.app.ai.tools.models import AIToolIntent, AIToolSpec

_MEMORY_QUERY_TOKENS = (
    "记得",
    "还记得",
    "喜欢什么",
    "偏好",
    "爱好",
    "之前说过",
)
_RELATIONSHIP_INSPECT_TOKENS = (
    "好感",
    "关系",
    "怎么看我",
    "讨厌我",
    "喜欢我",
    "态度",
)
_CAPABILITY_HELP_TOKENS = (
    "帮助",
    "help",
    "怎么用",
)
_PLUGIN_INSPECT_PATTERNS = (
    "怎么用",
    "插件",
)


def select_tools_for_message(
    *,
    message_text: str,
    available_tools: Iterable[AIToolSpec],
) -> list[AIToolSpec]:
    """Select a small set of relevant low-risk tools for one message."""

    normalized = message_text.strip().lower()
    if not normalized:
        return []

    tool_map = {tool.name: tool for tool in available_tools}
    selected: list[AIToolSpec] = []

    if _contains_any(normalized, _MEMORY_QUERY_TOKENS):
        tool = tool_map.get("memory.query")
        if tool is not None:
            selected.append(tool)

    if _contains_any(normalized, _RELATIONSHIP_INSPECT_TOKENS):
        tool = tool_map.get("relationship.inspect")
        if tool is not None:
            selected.append(tool)

    return selected


def plan_tool_intents_for_message(
    *,
    message_text: str,
    available_tools: Iterable[AIToolSpec],
) -> list["AIToolIntent"]:
    """Plan structured tool intents for the current message."""

    from apeiria.app.ai.tools.models import (
        AIMemoryQueryObservationInput,
        AINoneBotCapabilityRequest,
        AIPluginInspectCapabilityInput,
        AIToolIntent,
    )

    selected_tools = select_tools_for_message(
        message_text=message_text,
        available_tools=available_tools,
    )
    tool_map = {tool.name: tool for tool in available_tools}
    intents: list[AIToolIntent] = []
    for tool in selected_tools:
        if tool.name == "memory.query":
            intents.append(
                AIToolIntent(
                    tool_name=tool.name,
                    kind="observe_read_only",
                    input_payload=AIMemoryQueryObservationInput(
                        query_text=message_text,
                    ),
                )
            )
            continue
        if tool.name == "relationship.inspect":
            intents.append(
                AIToolIntent(
                    tool_name=tool.name,
                    kind="observe_read_only",
                    input_payload={},
                )
            )
            continue
        if tool.name == "plugin.capability" and _contains_any(
            message_text.lower(),
            _CAPABILITY_HELP_TOKENS,
        ):
            intents.append(
                AIToolIntent(
                    tool_name=tool.name,
                    kind="invoke_capability",
                    input_payload=AINoneBotCapabilityRequest(
                        capability_name="help.show",
                        arguments={"topic": "plugins"},
                    ),
                )
            )
    capability_tool = tool_map.get("plugin.capability")
    if capability_tool is not None and _contains_any(
        message_text.lower(),
        _CAPABILITY_HELP_TOKENS,
    ):
        intents.append(
            AIToolIntent(
                tool_name=capability_tool.name,
                kind="invoke_capability",
                input_payload=AINoneBotCapabilityRequest(
                    capability_name="help.show",
                    arguments={"topic": "plugins"},
                ),
                )
            )
        plugin_query = _extract_plugin_query(message_text)
        if plugin_query:
            intents.append(
                AIToolIntent(
                    tool_name=capability_tool.name,
                    kind="invoke_capability",
                    input_payload=AINoneBotCapabilityRequest(
                        capability_name="plugin.inspect",
                        arguments=AIPluginInspectCapabilityInput(
                            plugin_query=plugin_query,
                        ).__dict__,
                    ),
                )
            )
    return intents


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _extract_plugin_query(text: str) -> str | None:
    normalized = text.strip()
    if not normalized:
        return None
    if "怎么用" in normalized:
        query = normalized.split("怎么用", 1)[0].strip(" ，。！？!?")
        return _normalize_plugin_query(query)
    if "插件" in normalized and _contains_any(normalized, _PLUGIN_INSPECT_PATTERNS):
        query = normalized.split("插件", 1)[0].strip(" ，。！？!?")
        return _normalize_plugin_query(query)
    return None


def _normalize_plugin_query(query: str) -> str | None:
    normalized = query.strip()
    if not normalized:
        return None
    if normalized in {"帮助", "help", "帮我看看帮助"}:
        return None
    if normalized.startswith("帮我看看"):
        normalized = normalized.removeprefix("帮我看看").strip()
    return normalized or None
