"""Runtime persistence steps extracted from the orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from apeiria.ai.diagnostics import (
    sanitize_runtime_diagnostic,
    sanitize_runtime_diagnostics,
)
from apeiria.app.ai.pipeline.context_window_steps import build_and_store_context_window
from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
from apeiria.app.ai.pipeline.tool_steps import append_tool_observation_turns
from apeiria.app.ai.session_runtime import (
    RuntimeHardRuleDecision,
    RuntimeHardRuleReasonCode,
    project_turn_trace,
)
from apeiria.conversation.service import ChatMessageCreate, chat_session_service

if TYPE_CHECKING:
    from apeiria.app.ai.agent_turn import AgentTurnResult
    from apeiria.app.ai.pipeline.generation_steps import (
        ReplyGeneration,
        ReplyInputs,
        ReplyPreparation,
    )
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
    from apeiria.conversation.models import ChatSessionIdentity


@dataclass(frozen=True, slots=True)
class AssistantReplyPersistenceStage:
    """Persist generated reply state in explicit commit substeps."""

    async def persist_tool_observations(
        self,
        *,
        request: "AIRuntimeReplyRequest",
        generation: "ReplyGeneration",
        trace_id: str,
    ) -> str:
        if not generation.skill_runtime.turns:
            return "not_required"
        await append_tool_observation_turns(
            identity=request.identity,
            trace_id=trace_id,
            tool_turns=generation.skill_runtime.turns,
        )
        return "committed"

    async def persist_assistant_message(  # noqa: PLR0913
        self,
        *,
        request: "AIRuntimeReplyRequest",
        inputs: "ReplyInputs",
        social_decision: "ReplyStrategyDecision",
        plan: "ReplyPreparation",
        generation: "ReplyGeneration",
        trace_id: str,
    ) -> None:
        response = generation.response
        if response is None:
            return

        identity = request.identity
        delivery = generation.delivery_result
        await chat_session_service.append_message(
            identity,
            ChatMessageCreate(
                author_role="assistant",
                author_id=request.sender_id,
                text_content=response.content.strip(),
                meta=sanitize_runtime_diagnostics(
                    {
                        "trace_id": trace_id,
                        "source_id": response.source_id,
                        "model_name": response.model_name,
                        "task_class": (
                            generation.post_tool_task_class
                            if generation.skill_runtime.turns
                            else plan.pre_tool_task_class
                        ),
                        "recalled_memory_count": len(inputs.recalled_memories),
                        "tool_observation_count": len(generation.skill_runtime.turns),
                        "social_action": social_decision.action,
                        "social_tool_mode": social_decision.tool_mode,
                        "social_reason_text": social_decision.reason_text,
                        "social_reason_codes": list(social_decision.reason_codes),
                        "social_policy_source": social_decision.evidence.get(
                            "policy_source"
                        ),
                        "runtime_mode": request.runtime_mode,
                        "future_task_id": (
                            request.future_task.task_id if request.future_task else None
                        ),
                        "future_task_status": (
                            request.future_task.status if request.future_task else None
                        ),
                        "delivery_channel": delivery.channel if delivery else None,
                        "delivery_delivered": delivery.delivered if delivery else None,
                        "delivery_error": delivery.error if delivery else None,
                        "delivery_remote_message_id": (
                            delivery.remote_message_id if delivery else None
                        ),
                        **_turn_trace_meta(
                            trace_id=trace_id,
                            session_id=identity.session_id,
                            runtime_mode=request.runtime_mode,
                            social_decision=social_decision,
                            turn=generation.turn_result,
                            delivery_delivered=(
                                delivery.delivered if delivery else None
                            ),
                        ),
                        **_agent_turn_meta(generation.turn_result),
                    }
                ),
            ),
        )

    async def rebuild_context_window(
        self,
        *,
        identity: "ChatSessionIdentity",
    ) -> None:
        await build_and_store_context_window(identity=identity)


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

    stage = AssistantReplyPersistenceStage()
    await stage.persist_tool_observations(
        request=request,
        generation=gen,
        trace_id=trace_id,
    )
    await stage.persist_assistant_message(
        request=request,
        inputs=inputs,
        social_decision=social_decision,
        plan=prep,
        generation=gen,
        trace_id=trace_id,
    )
    await stage.rebuild_context_window(identity=request.identity)


def _turn_trace_meta(  # noqa: PLR0913
    *,
    trace_id: str,
    session_id: str,
    runtime_mode: str,
    social_decision: "ReplyStrategyDecision",
    turn: "AgentTurnResult | None",
    delivery_delivered: bool | None,
) -> dict[str, object]:
    decision = RuntimeHardRuleDecision(
        action="continue" if social_decision.should_speak else "observe",
        reason_codes=cast(
            "tuple[RuntimeHardRuleReasonCode, ...]",
            tuple(str(code) for code in social_decision.reason_codes),
        ),
        reason_text=social_decision.reason_text,
        evidence=social_decision.evidence,
        should_observe=True,
        should_reply=social_decision.should_speak,
    )
    trace = project_turn_trace(
        trace_id=trace_id,
        session_id=session_id,
        runtime_mode=runtime_mode,
        strategy_decision=decision,
        turn_result=turn,
        delivery_result=_delivery_result_from_bool(delivered=delivery_delivered),
    )
    return {"turn_trace": sanitize_runtime_diagnostic(trace.to_metadata())}


def _delivery_result_from_bool(*, delivered: bool | None) -> DeliveryOutcome | None:
    if delivered is None:
        return None
    return DeliveryOutcome(delivered=delivered)


def _agent_turn_meta(turn: "AgentTurnResult | None") -> dict[str, object]:
    if turn is None:
        return {}
    return sanitize_runtime_diagnostics(
        {
            "agent_turn_status": turn.status,
            "agent_turn_finish_reason": turn.finish_reason,
            "agent_turn_response_source": turn.response_source,
            "agent_turn_model_attempts": [
                {
                    "index": attempt.attempt_index,
                    "model_ref": attempt.model_ref,
                    "status": attempt.status,
                    "response_source": attempt.response_source,
                    "reason": attempt.reason,
                    "diagnostic": attempt.diagnostic,
                    "capability_observation": (
                        attempt.capability_observation.to_metadata()
                        if attempt.capability_observation is not None
                        else None
                    ),
                }
                for attempt in turn.model_attempts
            ],
            "agent_turn_tool_attempts": [
                {
                    "tool_call_id": attempt.tool_call_id,
                    "tool_name": attempt.tool_name,
                    "status": attempt.status,
                    "arguments_summary": attempt.arguments_summary,
                    "repetition_count": attempt.repetition_count,
                    "repeated": attempt.repeated,
                    "diagnostic": attempt.diagnostic,
                    "observation": attempt.observation.content,
                    "observation_truncated": attempt.observation.truncated,
                    "observation_original_length": attempt.observation.original_length,
                }
                for attempt in turn.tool_attempts
            ],
            "agent_turn_metadata": turn.metadata,
        }
    )
