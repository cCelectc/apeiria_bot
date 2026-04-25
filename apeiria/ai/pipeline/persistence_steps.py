"""Runtime persistence steps extracted from the orchestration layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.conversation.service import ChatMessageCreate, chat_session_service
from apeiria.ai.pipeline.context_window_steps import build_and_store_context_window

if TYPE_CHECKING:
    from apeiria.ai.pipeline.generation_steps import (
        ReplyGeneration,
        ReplyInputs,
        ReplyPreparation,
    )
    from apeiria.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.ai.reply_strategy import ReplyStrategyDecision


async def persist_reply(  # noqa: PLR0913
    *,
    request: "AIRuntimeReplyRequest",
    inputs: "ReplyInputs",
    social_decision: "ReplyStrategyDecision",
    prep: "ReplyPreparation",
    gen: "ReplyGeneration",
    trace_id: str,
) -> None:
    """Write the assistant message with full trace/social/delivery meta,
    then rebuild the context window so next turn sees the fresh reply."""

    response = gen.response
    if response is None:
        return

    identity = request.identity
    delivery = gen.delivery_result
    await chat_session_service.append_message(
        identity,
        ChatMessageCreate(
            author_role="assistant",
            author_id=request.sender_id,
            text_content=response.content.strip(),
            meta={
                "trace_id": trace_id,
                "source_id": response.source_id,
                "model_name": response.model_name,
                "task_class": (
                    gen.post_tool_task_class
                    if gen.skill_runtime.turns
                    else prep.pre_tool_task_class
                ),
                "recalled_memory_count": len(inputs.recalled_memories),
                "tool_observation_count": len(gen.skill_runtime.turns),
                "social_action": social_decision.action,
                "social_tool_mode": social_decision.tool_mode,
                "social_reason_text": social_decision.reason_text,
                "social_reason_codes": list(social_decision.reason_codes),
                "social_policy_source": social_decision.evidence.get("policy_source"),
                "runtime_mode": request.runtime_mode,
                "future_task_id": (
                    request.future_task.task_id if request.future_task else None
                ),
                "future_task_status": (
                    request.future_task.status if request.future_task else None
                ),
                "delivery_channel": None,
                "delivery_delivered": delivery.delivered if delivery else None,
                "delivery_error": delivery.error if delivery else None,
                "delivery_remote_message_id": None,
            },
        ),
    )
    await build_and_store_context_window(identity=identity)
