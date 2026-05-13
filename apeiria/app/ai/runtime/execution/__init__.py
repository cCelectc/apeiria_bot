"""Runtime execution stage for direct and tool-capable AI turns."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal

from apeiria.ai.config import get_ai_plugin_config
from apeiria.app.ai.agent_turn import AgentTurnResult
from apeiria.app.ai.runtime.execution.tool_loop import (
    RuntimeToolLoopInput,
    RuntimeToolLoopResult,
    runtime_tool_loop_runner,
)
from apeiria.app.ai.runtime.planning.model_selection import (
    GenerationRequest,
    generate_model_turn,
    select_fallback_models,
    select_model,
)
from apeiria.app.ai.runtime.planning.prompts import build_roleplay_reply_messages
from apeiria.app.ai.runtime.planning.reasoning import reasoning_options_for_task_class
from apeiria.app.ai.runtime.planning.reply_decision import (
    select_post_tool_reply_task_class,
)
from apeiria.app.ai.runtime.planning.tool_exposure import (
    compile_tool_exposure_provider_schema,
)

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelGenerateResponse, AIModelTaskClass
    from apeiria.app.ai.runtime.session.context import TurnContext
    from apeiria.app.ai.runtime.stages import (
        RuntimeExecutionOutcome,
        RuntimeTurnPlan,
    )


async def execute_runtime_turn(
    *,
    turn_context: "TurnContext",
    plan: "RuntimeTurnPlan",
) -> "RuntimeExecutionOutcome":
    """Execute one planned runtime turn from native context and plan only."""

    if plan.has_executable_tools:
        return await execute_tool_capable_runtime_turn(
            turn_context=turn_context,
            plan=plan,
        )
    return await execute_direct_runtime_turn(
        turn_context=turn_context,
        plan=plan,
        stream_sink=turn_context.stream_sink,
    )


async def execute_direct_runtime_turn(
    *,
    turn_context: "TurnContext",
    plan: "RuntimeTurnPlan",
    stream_sink: Any | None = None,
) -> "RuntimeExecutionOutcome":
    from apeiria.app.ai.runtime.stages import RuntimeExecutionOutcome

    turn_result = await _run_direct_model_turn(
        turn_context=turn_context,
        plan=plan,
        stream_sink=stream_sink,
    )
    return RuntimeExecutionOutcome(
        stage="execution",
        response=turn_result.response,
        skill_runtime=plan.skill_runtime,
        post_tool_task_class=None,
        delivery_result=None,
        turn_result=turn_result,
    )


async def _run_direct_model_turn(
    *,
    turn_context: "TurnContext",
    plan: "RuntimeTurnPlan",
    stream_sink: Any | None = None,
) -> AgentTurnResult:
    stream_policy = _direct_reply_stream_policy(
        turn_context=turn_context,
        plan=plan,
        stream_sink=stream_sink,
    )
    result = await generate_model_turn(
        GenerationRequest(
            selected=plan.selected,
            messages=turn_context.prompt_messages,
            trace_id=turn_context.trace_id,
            session_id=turn_context.session_id,
            tools=(),
            failure_stage="reply generation failed",
            runtime_mode=turn_context.runtime_mode,
            response_source="direct",
            fallback_models=plan.fallback_models,
            stream_policy=stream_policy,
            stream_sink=stream_sink if stream_policy != "none" else None,
            reasoning_options=reasoning_options_for_task_class(
                plan.pre_tool_task_class
            ),
        )
    )
    return _with_prompt_diagnostics(result.turn, turn_context)


def _direct_reply_stream_policy(
    *,
    turn_context: "TurnContext",
    plan: "RuntimeTurnPlan",
    stream_sink: Any | None,
) -> Literal["none", "optional"]:
    if stream_sink is None:
        return "none"
    if turn_context.delivery_target.delivery_channel != "webchat":
        return "none"
    capabilities = getattr(plan.selected, "resolved_capabilities", None)
    if not bool(getattr(capabilities, "supports_streaming", False)):
        return "none"
    return "optional"


async def execute_tool_capable_runtime_turn(
    *,
    turn_context: "TurnContext",
    plan: "RuntimeTurnPlan",
) -> "RuntimeExecutionOutcome":
    from apeiria.app.ai.runtime.stages import RuntimeExecutionOutcome

    skill_runtime = await _run_tool_loop(
        turn_context=turn_context,
        plan=plan,
    )
    response = skill_runtime.final_response
    turn_result = _build_tool_loop_turn_result(
        trace_id=turn_context.trace_id,
        runtime_mode=turn_context.runtime_mode,
        skill_runtime=skill_runtime,
    )
    turn_result = _with_prompt_diagnostics(turn_result, turn_context)

    post_tool_task_class: AIModelTaskClass | None = None
    if skill_runtime.turns:
        post_tool_task_class = select_post_tool_reply_task_class()
        response, turn_result = await _maybe_refine_tool_response(
            turn_context=turn_context,
            plan=plan,
            skill_runtime=skill_runtime,
            base=turn_result,
            post_tool_task_class=post_tool_task_class,
        )

    return RuntimeExecutionOutcome(
        stage="execution",
        response=response,
        skill_runtime=skill_runtime,
        post_tool_task_class=post_tool_task_class,
        delivery_result=None,
        turn_result=turn_result,
    )


async def _run_tool_loop(
    *,
    turn_context: "TurnContext",
    plan: "RuntimeTurnPlan",
) -> RuntimeToolLoopResult:
    recalled_memories = tuple(
        plan.reply_compose_input.memories if plan.reply_compose_input else ()
    )
    exposure_plan = plan.tool_exposure_plan
    return await runtime_tool_loop_runner.run(
        RuntimeToolLoopInput(
            session_id=turn_context.session_id,
            source_message_id=turn_context.source.source_message_id,
            trace_id=turn_context.trace_id,
            message_text=turn_context.source.message_text,
            tool_policy=turn_context.tool_policy,
            recalled_memory_ids=tuple(memory.memory_id for memory in recalled_memories),
            recalled_memory_contents=tuple(
                memory.content for memory in recalled_memories
            ),
            relationship_context=(
                plan.reply_compose_input.relationship
                if plan.reply_compose_input
                else None
            ),
            current_time=turn_context.current_time,
            runtime_mode=turn_context.runtime_mode,
            tool_mode=plan.tool_mode,
            execution_timeout_seconds=plan.tool_execution_timeout_seconds
            or get_ai_plugin_config().tool_execution_timeout_seconds,
            executable_tool_names=frozenset(exposure_plan.selected_tool_names),
            provider_name_map=exposure_plan.provider_name_map,
            messages=turn_context.prompt_messages,
            tools=compile_tool_exposure_provider_schema(
                exposure_plan,
                current_time=turn_context.current_time,
            ),
            selected=plan.selected,
            fallback_models=plan.fallback_models,
            reasoning_options=reasoning_options_for_task_class(
                plan.pre_tool_task_class
            ),
        )
    )


async def _maybe_refine_tool_response(
    *,
    turn_context: "TurnContext",
    plan: "RuntimeTurnPlan",
    skill_runtime: RuntimeToolLoopResult,
    base: AgentTurnResult,
    post_tool_task_class: "AIModelTaskClass",
) -> tuple["AIModelGenerateResponse | None", AgentTurnResult]:
    base_response = base.response
    if base_response is None or not base_response.content.strip():
        return base_response, base
    if plan.reply_compose_input is None:
        return base_response, base

    roleplay_selected = await select_model(
        task_class=post_tool_task_class,
        target=turn_context.model_target,
    )
    selected = roleplay_selected or plan.selected
    refinement = await generate_model_turn(
        GenerationRequest(
            selected=selected,
            messages=build_roleplay_reply_messages(
                replace(
                    plan.reply_compose_input,
                    tool_policy=skill_runtime.policy_text,
                    tool_results=skill_runtime.result_lines,
                )
            ),
            trace_id=turn_context.trace_id,
            session_id=turn_context.session_id,
            tools=(),
            failure_stage="reply generation failed after tool calls",
            runtime_mode=turn_context.runtime_mode,
            response_source="refinement",
            fallback_models=await select_fallback_models(selected),
            reasoning_options=reasoning_options_for_task_class(post_tool_task_class),
        )
    )
    return (
        refinement.response or base_response,
        _merge_refinement_turn_result(
            base=base,
            refinement=refinement.turn,
        ),
    )


def _with_prompt_diagnostics(
    turn_result: AgentTurnResult,
    turn_context: "TurnContext",
) -> AgentTurnResult:
    if not turn_context.prompt_diagnostics:
        return turn_result
    return replace(
        turn_result,
        metadata={
            **turn_result.metadata,
            "prompt_diagnostics": turn_context.prompt_diagnostics,
        },
    )


def _build_tool_loop_turn_result(
    *,
    trace_id: str,
    runtime_mode: str,
    skill_runtime: RuntimeToolLoopResult,
) -> AgentTurnResult:
    response = skill_runtime.final_response
    has_reply = response is not None and bool((response.content or "").strip())
    return AgentTurnResult(
        trace_id=trace_id,
        runtime_mode=runtime_mode,
        status="completed" if has_reply else "failed",
        finish_reason=skill_runtime.finish_reason,
        model_attempts=skill_runtime.model_attempts,
        tool_attempts=skill_runtime.tool_attempts,
        response=response,
        response_source="tool_loop",
        metadata={
            "tool_observation_count": len(skill_runtime.turns),
            "tool_message_count": len(skill_runtime.tool_messages),
            **skill_runtime.diagnostics,
        },
    )


def _merge_refinement_turn_result(
    *,
    base: AgentTurnResult,
    refinement: AgentTurnResult,
) -> AgentTurnResult:
    response = refinement.response or base.response
    used_refinement = refinement.response is not None
    metadata = {
        **base.metadata,
        "tool_loop_finish_reason": base.finish_reason,
        "refinement_finish_reason": refinement.finish_reason,
    }
    return AgentTurnResult(
        trace_id=base.trace_id,
        runtime_mode=base.runtime_mode,
        status=refinement.status if used_refinement else base.status,
        finish_reason=(
            refinement.finish_reason if used_refinement else base.finish_reason
        ),
        model_attempts=(*base.model_attempts, *refinement.model_attempts),
        tool_attempts=base.tool_attempts,
        response=response,
        response_source="refinement" if used_refinement else base.response_source,
        diagnostic=(
            None if used_refinement else refinement.diagnostic or base.diagnostic
        ),
        metadata=metadata,
    )


__all__ = [
    "execute_direct_runtime_turn",
    "execute_runtime_turn",
    "execute_tool_capable_runtime_turn",
]
