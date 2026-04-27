"""Assistant/tool message-chain validation for tool-loop model calls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.model.runtime.adapter import AIModelMessage
from apeiria.ai.tools.function_calling import function_name_to_tool_name

if TYPE_CHECKING:
    from apeiria.ai.tools.loop.state import ToolLoopState


def repair_tool_message_history(
    messages: tuple[AIModelMessage, ...],
    *,
    loop_state: ToolLoopState,
) -> tuple[AIModelMessage, ...]:
    """Return provider-valid assistant/tool message history."""

    tool_results_by_id = {
        message.tool_call_id: message
        for message in messages
        if message.role == "tool" and message.tool_call_id
    }
    referenced_call_ids = {
        tool_call.tool_call_id
        for message in messages
        if message.role == "assistant"
        for tool_call in message.tool_calls
    }
    orphan_count = sum(
        1
        for message in messages
        if message.role == "tool" and message.tool_call_id not in referenced_call_ids
    )
    loop_state.chain_repair_orphans += orphan_count

    repaired: list[AIModelMessage] = []
    for message in messages:
        if message.role == "tool":
            continue

        repaired.append(message)
        if message.role != "assistant" or not message.tool_calls:
            continue

        for tool_call in message.tool_calls:
            tool_result = tool_results_by_id.get(tool_call.tool_call_id)
            if tool_result is not None:
                repaired.append(tool_result)
                continue
            tool_name = function_name_to_tool_name(tool_call.name)
            loop_state.chain_repair_placeholders += 1
            repaired.append(
                AIModelMessage(
                    role="tool",
                    content=f"- [{tool_name}] skipped: missing tool observation",
                    tool_call_id=tool_call.tool_call_id,
                )
            )

    return tuple(repaired)
