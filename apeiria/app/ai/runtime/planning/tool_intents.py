"""Application-owned model orchestration for tool intent previews."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from apeiria.ai.model import model_invoker
from apeiria.ai.prompting import (
    ToolIntentPlanningPromptInput,
    build_tool_intent_planning_packet,
    render_messages,
)
from apeiria.ai.tools import AIToolIntentPreview, ai_tool_service
from apeiria.ai.tools.function_calling import (
    build_function_tools,
    build_intents_from_tool_calls,
)
from apeiria.app.ai.runtime.planning.model_selection import select_task_model

if TYPE_CHECKING:
    from apeiria.ai.tools import AIToolIntent, AIToolPolicy


async def plan_runtime_tool_intents(
    *,
    message_text: str,
    policy: "AIToolPolicy",
    recalled_memory_ids: tuple[str, ...] = (),
    recalled_memory_contents: tuple[str, ...] = (),
    relationship_context: str | None = None,
) -> list["AIToolIntent"]:
    """Plan tool intents through app-owned model selection and invocation."""

    allowed_tools = ai_tool_service.list_allowed_tools(policy)
    if not allowed_tools:
        return []

    selected = await select_task_model(task_class="tool_orchestration")
    if selected is None:
        return []

    try:
        response = await model_invoker.generate_text(
            selected=selected,
            messages=render_messages(
                build_tool_intent_planning_packet(
                    ToolIntentPlanningPromptInput(
                        message_text=message_text,
                        recalled_memory_ids=recalled_memory_ids,
                        recalled_memory_contents=recalled_memory_contents,
                        relationship_context=relationship_context,
                    )
                )
            ),
            tools=build_function_tools(allowed_tools),
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).debug("Tool intent model call failed")
        return []
    if response is None:
        return []

    return [
        intent
        for intent in build_intents_from_tool_calls(response.tool_calls)
        if intent.tool_name != "memory.write"
        or _memory_update_is_recalled(intent, recalled_memory_ids)
    ]


async def preview_runtime_tool_intents(
    *,
    message_text: str,
    policy: "AIToolPolicy",
    recalled_memory_ids: tuple[str, ...] = (),
    recalled_memory_contents: tuple[str, ...] = (),
    relationship_context: str | None = None,
) -> list[AIToolIntentPreview]:
    """Project app-planned tool intents for admin diagnostics."""

    intents = await plan_runtime_tool_intents(
        message_text=message_text,
        policy=policy,
        recalled_memory_ids=recalled_memory_ids,
        recalled_memory_contents=recalled_memory_contents,
        relationship_context=relationship_context,
    )
    return [
        AIToolIntentPreview(
            tool_name=intent.tool_name,
            kind=intent.kind,
            reason=intent.reason,
            input_payload=_to_jsonable_payload(intent.input_payload),
        )
        for intent in intents
    ]


def _memory_update_is_recalled(
    intent: "AIToolIntent",
    recalled_memory_ids: tuple[str, ...],
) -> bool:
    if isinstance(intent.input_payload, dict):
        memory_id = intent.input_payload.get("memory_id")
    else:
        memory_id = getattr(intent.input_payload, "memory_id", None)
    if not isinstance(memory_id, str):
        return True
    return memory_id in recalled_memory_ids


def _to_jsonable_payload(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    return payload


__all__ = [
    "plan_runtime_tool_intents",
    "preview_runtime_tool_intents",
]
