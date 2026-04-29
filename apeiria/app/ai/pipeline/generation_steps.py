"""Runtime generation-stage dataclasses and gather step."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.config import get_ai_plugin_config
from apeiria.ai.prompting import (
    project_reply_prompt_regions,
    prompt_region_diagnostics,
)
from apeiria.ai.skills import ai_skill_service
from apeiria.ai.tools import (
    ToolGatewayRequest,
    ToolGatewayResult,
    tool_gateway,
)
from apeiria.app.ai.agent_turn import AgentTurnResult
from apeiria.app.ai.pipeline.composer import (
    AIRuntimeComposeInput,
    build_pre_tool_reply_messages,
    build_pre_tool_reply_packet,
    build_roleplay_reply_messages,
)
from apeiria.app.ai.pipeline.context_window_steps import record_context_usage
from apeiria.app.ai.pipeline.delivery_steps import (
    DeliveryOutcome,
    deliver_generated_reply,
)
from apeiria.app.ai.pipeline.model_steps import (
    GenerationRequest,
    build_no_model_diagnostic,
    generate_model_turn,
    select_pipeline_fallback_models,
    select_pipeline_model,
)
from apeiria.app.ai.pipeline.persona_steps import build_model_binding_target
from apeiria.app.ai.pipeline.routing import (
    select_post_tool_reply_task_class,
    select_pre_tool_reply_task_class,
)
from apeiria.app.ai.pipeline.tool_steps import append_tool_observation_turns
from apeiria.app.ai.reply_strategy import summarize_reply_strategy_decision
from apeiria.app.ai.session_runtime import (
    RuntimeAgentRunner,
    ToolGatewayMigrationAdapter,
)

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import (
        AIModelGenerateResponse,
        AIModelMessage,
        AIModelTaskClass,
        AISelectedModel,
    )
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.app.ai.pipeline.input_steps import ReplyInputs
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
    from apeiria.app.ai.session_runtime import TurnContext


@dataclass(frozen=True)
class ReplyPreparation:
    """Resources resolved before the model generates a reply."""

    skill_runtime: ToolGatewayResult
    selected: "AISelectedModel"
    skill_activation: str | None
    pre_tool_task_class: "AIModelTaskClass"


@dataclass(frozen=True)
class ReplyGeneration:
    """Final model response plus outbound delivery outcome for this turn."""

    response: "AIModelGenerateResponse | None"
    skill_runtime: ToolGatewayResult
    post_tool_task_class: "AIModelTaskClass | None"
    delivery_result: DeliveryOutcome | None
    turn_result: AgentTurnResult | None = None


async def prepare_generation(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    current_time: "datetime",
    trace_id: str,
) -> ReplyPreparation | None:
    """Resolve tools, select a model, and pick prompt-level skills."""

    identity = request.identity
    tool_execution_timeout_seconds = (
        get_ai_plugin_config().tool_execution_timeout_seconds
    )

    skill_runtime = await tool_gateway.prepare(
        ToolGatewayRequest(
            session_id=identity.session_id,
            source_message_id=request.source_message_id,
            trace_id=trace_id,
            message_text=request.message_text,
            policy=inputs.tool_policy,
            recalled_memories=tuple(inputs.recalled_memories),
            relationship_context=inputs.relationship_context,
            current_time=current_time,
            tool_mode=social_decision.tool_mode,
            execution_timeout_seconds=tool_execution_timeout_seconds,
        ),
    )
    pre_tool_task_class = select_pre_tool_reply_task_class(
        has_tools=bool(skill_runtime.available_tools),
    )
    selected = await select_pipeline_model(
        task_class=pre_tool_task_class,
        target=inputs.model_target,
    )
    if selected is None:
        logger.debug(
            build_no_model_diagnostic(
                trace_id=trace_id,
                session_id=identity.session_id,
                task_class=pre_tool_task_class,
            )
        )
        return None

    skill_selection = await ai_skill_service.select_skills(
        message_text=request.message_text,
        conversation_summary=inputs.conversation_summary,
    )
    return ReplyPreparation(
        skill_runtime=skill_runtime,
        selected=selected,
        skill_activation=skill_selection.activation_prompt,
        pre_tool_task_class=pre_tool_task_class,
    )


async def generate_reply(  # noqa: PLR0913
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    prep: ReplyPreparation,
    current_time: "datetime",
    trace_id: str,
    turn_context: "TurnContext | None" = None,
) -> ReplyGeneration:
    """Generate a reply via direct or tool-loop path and deliver it if needed."""

    if prep.skill_runtime.available_tools:
        if turn_context is not None:
            return await _generate_tool_capable_turn_context(
                request=request,
                inputs=inputs,
                social_decision=social_decision,
                prep=prep,
                current_time=current_time,
                trace_id=trace_id,
                turn_context=turn_context,
            )
        return await _generate_with_tool_loop(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
            current_time=current_time,
            trace_id=trace_id,
        )
    return await _generate_direct(
        request=request,
        inputs=inputs,
        social_decision=social_decision,
        prep=prep,
        trace_id=trace_id,
        turn_context=turn_context,
    )


async def _generate_tool_capable_turn_context(  # noqa: PLR0913
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    prep: ReplyPreparation,
    current_time: "datetime",
    trace_id: str,
    turn_context: "TurnContext",
) -> ReplyGeneration:
    reply_generation: ReplyGeneration | None = None

    async def direct_executor(context: "TurnContext") -> AgentTurnResult:
        return AgentTurnResult.skipped(
            trace_id=context.trace_id,
            runtime_mode=context.runtime_mode,
            finish_reason="direct_executor_not_configured",
        )

    async def tool_capable_executor(context: "TurnContext") -> AgentTurnResult:
        nonlocal reply_generation
        reply_generation = await _generate_with_tool_loop(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
            current_time=current_time,
            trace_id=trace_id,
            turn_context=context,
        )
        tool_turn_result = reply_generation.turn_result
        if tool_turn_result is not None:
            tool_turn_result = _with_prompt_diagnostics(
                tool_turn_result,
                context,
            )
            reply_generation = replace(
                reply_generation,
                turn_result=tool_turn_result,
            )
            return tool_turn_result
        return AgentTurnResult.skipped(
            trace_id=context.trace_id,
            runtime_mode=context.runtime_mode,
            finish_reason="tool_loop_without_turn_result",
        )

    runner = RuntimeAgentRunner(
        direct_executor=direct_executor,
        tool_capable_executor=tool_capable_executor,
    )
    turn_result = await runner.run_turn(turn_context)
    if reply_generation is not None:
        return reply_generation
    return ReplyGeneration(
        response=turn_result.response,
        skill_runtime=prep.skill_runtime,
        post_tool_task_class=None,
        delivery_result=None,
        turn_result=turn_result,
    )


async def _generate_direct(  # noqa: PLR0913
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    prep: ReplyPreparation,
    trace_id: str,
    turn_context: "TurnContext | None" = None,
) -> ReplyGeneration:
    """Single-shot generation path (no tool loop)."""
    if turn_context is not None:
        turn_result = await _run_direct_turn_context(
            context=turn_context,
            prep=prep,
        )
        response = turn_result.response
        if response is None:
            return ReplyGeneration(
                response=None,
                skill_runtime=prep.skill_runtime,
                post_tool_task_class=None,
                delivery_result=None,
                turn_result=turn_result,
            )

        record_context_usage(
            request.identity.session_id,
            response=response,
            message_count=len(inputs.turns),
        )
        delivery_result = await deliver_generated_reply(
            request,
            response.content.strip() if response.content else "",
        )
        return ReplyGeneration(
            response=response,
            skill_runtime=prep.skill_runtime,
            post_tool_task_class=None,
            delivery_result=delivery_result,
            turn_result=turn_result,
        )

    turn = await generate_model_turn(
        GenerationRequest(
            selected=prep.selected,
            messages=build_pre_tool_reply_messages(
                _build_compose_input(
                    request=request,
                    inputs=inputs,
                    social_decision=social_decision,
                    skill_runtime=prep.skill_runtime,
                    skill_activation=prep.skill_activation,
                ),
                has_tools=False,
            ),
            trace_id=trace_id,
            session_id=request.identity.session_id,
            tools=(),
            failure_stage="reply generation failed",
            runtime_mode=request.runtime_mode,
            response_source="direct",
            fallback_models=await select_pipeline_fallback_models(prep.selected),
        )
    )
    response = turn.response
    if response is None:
        return ReplyGeneration(
            response=None,
            skill_runtime=prep.skill_runtime,
            post_tool_task_class=None,
            delivery_result=None,
            turn_result=turn.turn,
        )

    record_context_usage(
        request.identity.session_id,
        response=response,
        message_count=len(inputs.turns),
    )
    delivery_result = await deliver_generated_reply(
        request,
        response.content.strip() if response.content else "",
    )
    return ReplyGeneration(
        response=response,
        skill_runtime=prep.skill_runtime,
        post_tool_task_class=None,
        delivery_result=delivery_result,
        turn_result=turn.turn,
    )


async def _generate_with_tool_loop(  # noqa: PLR0913
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    prep: ReplyPreparation,
    current_time: "datetime",
    trace_id: str,
    turn_context: "TurnContext | None" = None,
) -> ReplyGeneration:
    """Messages-based multi-round tool calling flow with optional refinement."""

    compose_input = _build_compose_input(
        request=request,
        inputs=inputs,
        social_decision=social_decision,
        skill_runtime=prep.skill_runtime,
        skill_activation=prep.skill_activation,
    )
    messages = list(build_pre_tool_reply_messages(compose_input, has_tools=True))

    tool_request = ToolGatewayRequest(
        session_id=request.identity.session_id,
        source_message_id=request.source_message_id,
        trace_id=trace_id,
        message_text=request.message_text,
        policy=inputs.tool_policy,
        recalled_memories=tuple(inputs.recalled_memories),
        relationship_context=inputs.relationship_context,
        current_time=current_time,
        runtime_mode=request.runtime_mode,
        tool_mode=social_decision.tool_mode,
        execution_timeout_seconds=get_ai_plugin_config().tool_execution_timeout_seconds,
    )
    fallback_models = await select_pipeline_fallback_models(prep.selected)
    if turn_context is not None:
        skill_runtime = await ToolGatewayMigrationAdapter(
            gateway=tool_gateway
        ).run_tool_loop(
            request=tool_request,
            messages=tuple(messages),
            exposure_plan=turn_context.tool_exposure_plan,
            selected_model=prep.selected,
            fallback_models=fallback_models,
        )
    else:
        skill_runtime = await tool_gateway.run_tool_loop(
            tool_request,
            messages=messages,
            tools=prep.skill_runtime.available_tools,
            selected=prep.selected,
            fallback_models=fallback_models,
        )
    response = skill_runtime.final_response
    turn_result = _build_tool_loop_turn_result(
        trace_id=trace_id,
        runtime_mode=request.runtime_mode,
        skill_runtime=skill_runtime,
    )
    post_tool_task_class: AIModelTaskClass | None = None

    if response is not None:
        record_context_usage(
            request.identity.session_id,
            response=response,
            message_count=len(inputs.turns),
        )

    if skill_runtime.turns:
        await append_tool_observation_turns(
            identity=request.identity,
            trace_id=trace_id,
            tool_turns=skill_runtime.turns,
        )
        post_tool_task_class = select_post_tool_reply_task_class()

        if response is not None and response.content.strip():
            roleplay_selected = await select_pipeline_model(
                task_class=post_tool_task_class,
                target=build_model_binding_target(
                    request.identity,
                    request.user_id,
                ),
            )
            refinement = await generate_model_turn(
                GenerationRequest(
                    selected=roleplay_selected or prep.selected,
                    messages=build_roleplay_reply_messages(
                        AIRuntimeComposeInput(
                            persona=inputs.persona,
                            scene_type=request.identity.scene_type,
                            person_profile=inputs.person_profile,
                            relationship=inputs.relationship_context,
                            tool_policy=skill_runtime.policy_text,
                            tool_results=skill_runtime.result_lines,
                            memories=inputs.recalled_memories,
                            conversation_summary=inputs.conversation_summary,
                            social_policy_summary=(
                                summarize_reply_strategy_decision(social_decision)
                            ),
                            future_task_context=_build_future_task_context(
                                request.future_task
                            ),
                            turns=inputs.turns,
                        )
                    ),
                    trace_id=trace_id,
                    session_id=request.identity.session_id,
                    tools=(),
                    failure_stage="reply generation failed after tool calls",
                    runtime_mode=request.runtime_mode,
                    response_source="refinement",
                    fallback_models=await select_pipeline_fallback_models(
                        roleplay_selected or prep.selected
                    ),
                )
            )
            turn_result = _merge_refinement_turn_result(
                base=turn_result,
                refinement=refinement.turn,
            )
            if refinement.response is not None:
                response = refinement.response

    if response is None:
        return ReplyGeneration(
            response=None,
            skill_runtime=skill_runtime,
            post_tool_task_class=post_tool_task_class,
            delivery_result=None,
            turn_result=turn_result,
        )
    delivery_result = await deliver_generated_reply(
        request,
        response.content.strip() if response.content else "",
    )
    return ReplyGeneration(
        response=response,
        skill_runtime=skill_runtime,
        post_tool_task_class=post_tool_task_class,
        delivery_result=delivery_result,
        turn_result=turn_result,
    )


async def _run_direct_turn_context(
    *,
    context: "TurnContext",
    prep: ReplyPreparation,
) -> AgentTurnResult:
    fallback_models = await select_pipeline_fallback_models(prep.selected)

    async def direct_executor(context: "TurnContext") -> AgentTurnResult:
        result = await generate_model_turn(
            GenerationRequest(
                selected=prep.selected,
                messages=context.prompt_messages,
                trace_id=context.trace_id,
                session_id=context.session_id,
                tools=(),
                failure_stage="reply generation failed",
                runtime_mode=context.runtime_mode,
                response_source="direct",
                fallback_models=fallback_models,
            )
        )
        return _with_prompt_diagnostics(result.turn, context)

    async def tool_capable_executor(context: "TurnContext") -> AgentTurnResult:
        return AgentTurnResult.skipped(
            trace_id=context.trace_id,
            runtime_mode=context.runtime_mode,
            finish_reason="tool_executor_not_configured",
        )

    runner = RuntimeAgentRunner(
        direct_executor=direct_executor,
        tool_capable_executor=tool_capable_executor,
    )
    return await runner.run_turn(context)


def _with_prompt_diagnostics(
    turn_result: AgentTurnResult,
    context: "TurnContext",
) -> AgentTurnResult:
    if not context.prompt_diagnostics:
        return turn_result
    return replace(
        turn_result,
        metadata={
            **turn_result.metadata,
            "prompt_diagnostics": context.prompt_diagnostics,
        },
    )


def build_initial_reply_prompt_messages(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    prep: ReplyPreparation,
) -> tuple["AIModelMessage", ...]:
    """Build the first model prompt messages used by direct/tool planning."""

    return build_pre_tool_reply_messages(
        _initial_reply_compose_input(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
        ),
        has_tools=bool(prep.skill_runtime.available_tools),
    )


def build_initial_reply_prompt_diagnostics(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    prep: ReplyPreparation,
) -> dict[str, object]:
    """Build bounded prompt-region diagnostics for the first reply prompt."""

    packet = build_pre_tool_reply_packet(
        _initial_reply_compose_input(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
        ),
        has_tools=bool(prep.skill_runtime.available_tools),
    )
    return prompt_region_diagnostics(project_reply_prompt_regions(packet))


def _initial_reply_compose_input(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    prep: ReplyPreparation,
) -> AIRuntimeComposeInput:
    return _build_compose_input(
        request=request,
        inputs=inputs,
        social_decision=social_decision,
        skill_runtime=prep.skill_runtime,
        skill_activation=prep.skill_activation,
    )


def _build_tool_loop_turn_result(
    *,
    trace_id: str,
    runtime_mode: str,
    skill_runtime: ToolGatewayResult,
) -> AgentTurnResult:
    response = skill_runtime.final_response
    has_reply = response is not None and bool((response.content or "").strip())
    return AgentTurnResult(
        trace_id=trace_id,
        runtime_mode=runtime_mode,
        status="completed" if has_reply else "failed",
        finish_reason=skill_runtime.loop_finish_reason,
        model_attempts=skill_runtime.model_attempts,
        tool_attempts=skill_runtime.tool_attempts,
        response=response,
        response_source="tool_loop",
        metadata={
            "tool_observation_count": len(skill_runtime.turns),
            "tool_message_count": len(skill_runtime.tool_messages),
            **skill_runtime.metadata,
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


def _build_compose_input(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    skill_runtime: ToolGatewayResult,
    skill_activation: str | None,
) -> AIRuntimeComposeInput:
    return AIRuntimeComposeInput(
        persona=inputs.persona,
        scene_type=request.identity.scene_type,
        person_profile=inputs.person_profile,
        relationship=inputs.relationship_context,
        tool_policy=skill_runtime.policy_text,
        tool_results=skill_runtime.result_lines,
        memories=inputs.recalled_memories,
        conversation_summary=inputs.conversation_summary,
        social_policy_summary=summarize_reply_strategy_decision(social_decision),
        future_task_context=_build_future_task_context(request.future_task),
        skill_activation=skill_activation,
        turns=inputs.turns,
    )


def _build_future_task_context(
    task: "AIFutureTaskDefinition | None",
) -> str | None:
    if task is None:
        return None
    return "\n".join(
        (
            f"task_id={task.task_id}",
            f"title={task.title}",
            f"description={task.description}",
            f"trigger_at={task.trigger_at.isoformat()}",
            f"status={task.status}",
        )
    )
