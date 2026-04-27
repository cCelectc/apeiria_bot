"""Model-driven AI tool intent planning."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.tools.function_calling import (
    build_function_tools,
    build_intents_from_tool_calls,
)
from apeiria.ai.tools.selection import build_tool_planning_prompt

if TYPE_CHECKING:
    from apeiria.ai.tools.models import AIToolIntent, AIToolSpec


class AIToolIntentPlanner:
    """Plan tool intents through the selected tool-orchestration model."""

    async def plan_tool_intents(
        self,
        *,
        message_text: str,
        allowed_tools: list[AIToolSpec],
        recalled_memory_ids: tuple[str, ...],
        recalled_memory_contents: tuple[str, ...],
        relationship_context: str | None,
    ) -> list[AIToolIntent]:
        from apeiria.ai.model.gateway import model_gateway
        from apeiria.ai.model.models import AIModelRouteQuery

        if not allowed_tools:
            return []

        selected = await model_gateway.select_model(
            query=AIModelRouteQuery(task_class="tool_orchestration"),
        )
        if selected is None:
            return []

        response = await model_gateway.generate_native(
            selected=selected,
            prompt=build_tool_planning_prompt(
                message_text=message_text,
                recalled_memory_ids=recalled_memory_ids,
                recalled_memory_contents=recalled_memory_contents,
                relationship_context=relationship_context,
            ),
            tools=build_function_tools(allowed_tools),
        )
        if response is None:
            return []

        return [
            intent
            for intent in build_intents_from_tool_calls(response.tool_calls)
            if intent.tool_name != "memory.update"
            or _memory_update_is_recalled(intent, recalled_memory_ids)
        ]


def _memory_update_is_recalled(
    intent: AIToolIntent,
    recalled_memory_ids: tuple[str, ...],
) -> bool:
    if isinstance(intent.input_payload, dict):
        memory_id = intent.input_payload.get("memory_id")
    else:
        memory_id = getattr(intent.input_payload, "memory_id", None)
    if not isinstance(memory_id, str):
        return True
    return memory_id in recalled_memory_ids
