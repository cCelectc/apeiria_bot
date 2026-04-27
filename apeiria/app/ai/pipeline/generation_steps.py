"""Runtime generation-stage dataclasses and gather step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.config import get_ai_plugin_config
from apeiria.ai.skills import ai_skill_service
from apeiria.ai.tools import (
    ToolGatewayRequest,
    ToolGatewayResult,
    tool_gateway,
)
from apeiria.app.ai.pipeline.composer import (
    AIRuntimeComposeInput,
    build_runtime_prompt_channels,
    compose_pre_tool_reply_prompt,
    compose_roleplay_reply_prompt,
)
from apeiria.app.ai.pipeline.context_window_steps import record_context_usage
from apeiria.app.ai.pipeline.delivery_steps import (
    DeliveryOutcome,
    deliver_generated_reply,
)
from apeiria.app.ai.pipeline.message_builder import build_chat_messages
from apeiria.app.ai.pipeline.model_steps import (
    GenerationRequest,
    safe_generate_model,
    select_pipeline_model,
)
from apeiria.app.ai.pipeline.persona_steps import build_model_binding_target
from apeiria.app.ai.pipeline.routing import (
    select_post_tool_reply_task_class,
    select_pre_tool_reply_task_class,
)
from apeiria.app.ai.pipeline.tool_steps import append_tool_observation_turns
from apeiria.app.ai.reply_strategy import summarize_reply_strategy_decision

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import (
        AIModelGenerateResponse,
        AIModelTaskClass,
        AISelectedModel,
    )
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.app.ai.pipeline.input_steps import ReplyInputs
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.app.ai.reply_strategy import ReplyStrategyDecision


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
            "AI trace {} skipped reply: no model selected for session {}",
            trace_id,
            identity.session_id,
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
) -> ReplyGeneration:
    """Generate a reply via direct or tool-loop path and deliver it if needed."""

    if prep.skill_runtime.available_tools:
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
    )


async def _generate_direct(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    prep: ReplyPreparation,
    trace_id: str,
) -> ReplyGeneration:
    """Single-shot generation path (no tool loop)."""
    response = await safe_generate_model(
        GenerationRequest(
            selected=prep.selected,
            prompt=compose_pre_tool_reply_prompt(
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
        )
    )
    if response is None:
        return ReplyGeneration(
            response=None,
            skill_runtime=prep.skill_runtime,
            post_tool_task_class=None,
            delivery_result=None,
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
    )


async def _generate_with_tool_loop(  # noqa: PLR0913
    *,
    request: "AIRuntimeReplyRequest",
    inputs: ReplyInputs,
    social_decision: "ReplyStrategyDecision",
    prep: ReplyPreparation,
    current_time: "datetime",
    trace_id: str,
) -> ReplyGeneration:
    """Messages-based multi-round tool calling flow with optional refinement."""

    compose_input = _build_compose_input(
        request=request,
        inputs=inputs,
        social_decision=social_decision,
        skill_runtime=prep.skill_runtime,
        skill_activation=prep.skill_activation,
    )
    channels = build_runtime_prompt_channels(
        compose_input, mode="planner", include_tool_policy=True
    )
    messages = list(build_chat_messages(channels, inputs.turns))

    tool_request = ToolGatewayRequest(
        session_id=request.identity.session_id,
        source_message_id=request.source_message_id,
        trace_id=trace_id,
        message_text=request.message_text,
        policy=inputs.tool_policy,
        recalled_memories=tuple(inputs.recalled_memories),
        relationship_context=inputs.relationship_context,
        current_time=current_time,
        tool_mode=social_decision.tool_mode,
        execution_timeout_seconds=get_ai_plugin_config().tool_execution_timeout_seconds,
    )
    skill_runtime = await tool_gateway.run_tool_loop(
        tool_request,
        messages=messages,
        tools=prep.skill_runtime.available_tools,
        selected=prep.selected,
    )
    response = skill_runtime.final_response
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
            refinement = await safe_generate_model(
                GenerationRequest(
                    selected=roleplay_selected or prep.selected,
                    prompt=compose_roleplay_reply_prompt(
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
                )
            )
            if refinement is not None:
                response = refinement

    if response is None:
        return ReplyGeneration(
            response=None,
            skill_runtime=skill_runtime,
            post_tool_task_class=post_tool_task_class,
            delivery_result=None,
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
