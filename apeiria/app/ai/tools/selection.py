"""Pure helpers for selecting tools to observe or invoke."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.tools.intent_builders import build_capability_intents

if TYPE_CHECKING:
    from apeiria.app.ai.tools.models import AIToolIntent, AIToolSpec


def select_tools_for_message(
    message_text: str,
    available_tools: list["AIToolSpec"],
) -> list["AIToolSpec"]:
    """Return the subset of skills relevant to the current message."""

    lowered = message_text.lower()
    selected: list[AIToolSpec] = []
    for tool in available_tools:
        matched = False
        if tool.name == "memory.query":
            matched = any(
                token in lowered
                for token in ("remember", "memory", "recall", "之前", "记得")
            )
        elif tool.name == "relationship.inspect":
            matched = any(
                token in lowered for token in ("affinity", "mood", "关系", "好感")
            )
        elif tool.name == "plugin.capability":
            matched = any(
                token in lowered
                for token in ("plugin", "help", "inspect", "插件", "帮助")
            )

        if matched:
            selected.append(tool)
    return selected


def explain_tool_match(
    *,
    tool_name: str,
    message_text: str,
) -> str:
    """Explain why a tool matched the current message."""

    lowered = message_text.lower()
    if tool_name == "memory.query":
        if any(token in lowered for token in ("之前", "记得")):
            return "memory recall keyword detected"
        return "memory-related keyword detected"
    if tool_name == "relationship.inspect":
        return "relationship or mood keyword detected"
    if tool_name == "plugin.capability":
        return "plugin/help inspection keyword detected"
    return "tool selected by planner"


def plan_tool_intents_for_message(
    message_text: str,
    available_tools: list["AIToolSpec"],
) -> list["AIToolIntent"]:
    """Plan structured skill intents for the current message."""

    from apeiria.app.ai.tools.models import AIMemoryQueryObservationInput, AIToolIntent

    intents: list[AIToolIntent] = []
    selected_tools = select_tools_for_message(message_text, available_tools)

    for tool in selected_tools:
        if tool.name == "memory.query":
            intents.append(
                AIToolIntent(
                    tool_name=tool.name,
                    kind="observe_read_only",
                    input_payload=AIMemoryQueryObservationInput(
                        query_text=message_text
                    ),
                    reason=explain_tool_match(
                        tool_name=tool.name,
                        message_text=message_text,
                    ),
                )
            )
        elif tool.name == "relationship.inspect":
            intents.append(
                AIToolIntent(
                    tool_name=tool.name,
                    kind="observe_read_only",
                    input_payload=None,
                    reason=explain_tool_match(
                        tool_name=tool.name,
                        message_text=message_text,
                    ),
                )
            )
        elif tool.name == "plugin.capability":
            intents.extend(build_capability_intents(message_text))
    return intents
