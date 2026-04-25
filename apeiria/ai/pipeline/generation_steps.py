"""Runtime generation-stage dataclasses and gather step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.config import get_ai_plugin_config
from apeiria.ai.model import AIModelRouteQuery
from apeiria.ai.model.gateway import model_gateway
from apeiria.ai.pipeline.composer import (
    AIRuntimeComposeInput,
    build_runtime_prompt_channels,
    compose_pre_tool_reply_prompt,
    compose_roleplay_reply_prompt,
)
from apeiria.ai.pipeline.context_window_steps import (
    build_and_store_context_window,
    record_context_usage,
)
from apeiria.ai.pipeline.memory_steps import (
    load_person_profile_for_prompt,
    recall_memories,
)
from apeiria.ai.pipeline.message_builder import build_chat_messages
from apeiria.ai.pipeline.persona_steps import (
    build_model_binding_target,
    load_persona_bundle,
)
from apeiria.ai.pipeline.relationship_steps import (
    build_relationship_target,
    load_relationship_context,
    update_relationship_state,
)
from apeiria.ai.pipeline.reply_strategy_steps import resolve_initiative_bias
from apeiria.ai.pipeline.routing import (
    select_post_tool_reply_task_class,
    select_pre_tool_reply_task_class,
)
from apeiria.ai.pipeline.tool_steps import (
    append_tool_observation_turns,
    resolve_tool_policy,
)
from apeiria.ai.reply_strategy import summarize_reply_strategy_decision
from apeiria.ai.skills.service import ai_skill_service
from apeiria.ai.tools.gateway import (
    ToolGatewayRequest,
    ToolGatewayResult,
    tool_gateway,
)
from apeiria.ai.tools.service import ai_tool_service

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.conversation.models import ChatContextMessageView
    from apeiria.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.ai.memory.models import AIMemoryDefinition
    from apeiria.ai.model import AIModelBindingTarget
    from apeiria.ai.model.adapter import (
        AIModelGenerateResponse,
        AIModelToolDefinition,
    )
    from apeiria.ai.model.selection import AISelectedModel
    from apeiria.ai.pipeline.prompting import AIPersonaPromptBundleLike
    from apeiria.ai.pipeline.relationship_steps import AIRelationshipTarget
    from apeiria.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.ai.reply_strategy import ReplyStrategyDecision
    from apeiria.ai.tools.models import AIToolPolicy, AIToolSpec


@dataclass(frozen=True)
class ReplyInputs:
    """Aggregated prompt/context materials for one reply turn."""

    turns: list["ChatContextMessageView"]
    conversation_summary: str | None
    relationship_target: "AIRelationshipTarget"
    model_target: "AIModelBindingTarget"
    tool_policy: "AIToolPolicy"
    persona: "AIPersonaPromptBundleLike | None"
    recalled_memories: list["AIMemoryDefinition"]
    relationship_context: str | None
    person_profile: tuple[str, ...]
    allowed_tools: tuple["AIToolSpec", ...]
    initiative_bias: float


@dataclass(frozen=True)
class ReplyPreparation:
    """Resources resolved before the model generates a reply."""

    skill_runtime: ToolGatewayResult
    selected: "AISelectedModel"
    skill_activation: str | None
    pre_tool_task_class: str


@dataclass(frozen=True)
class DeliveryOutcome:
    """Outcome of a proactive (future_task) message delivery."""

    delivered: bool
    error: str | None = None


@dataclass(frozen=True)
class ReplyGeneration:
    """Final model response plus outbound delivery outcome for this turn."""

    response: "AIModelGenerateResponse | None"
    skill_runtime: ToolGatewayResult
    post_tool_task_class: str | None
    delivery_result: DeliveryOutcome | None


@dataclass(frozen=True)
class _GenerationRequest:
    """One model generation request with trace metadata."""

    selected: "AISelectedModel"
    prompt: str
    trace_id: str
    session_id: str
    tools: tuple["AIModelToolDefinition", ...]
    failure_stage: str


async def gather_reply_inputs(
    request: "AIRuntimeReplyRequest",
    current_time: "datetime",
) -> ReplyInputs:
    """Collect all prompt-facing materials needed to decide and generate a reply."""

    identity = request.identity

    turns, conversation_summary = await build_and_store_context_window(
        identity=identity,
    )
    relationship_target = build_relationship_target(identity, request.user_id)
    model_target = build_model_binding_target(identity, request.user_id)
    tool_policy = await resolve_tool_policy(
        identity,
        is_tome=request.is_tome,
    )
    persona = await load_persona_bundle(
        request=request,
        current_time=current_time,
        turns=turns,
    )
    if request.runtime_mode == "message" and request.sentiment is not None:
        await update_relationship_state(
            target=relationship_target,
            sentiment=request.sentiment,
            is_tome=request.is_tome,
        )
    recalled_memories = await recall_memories(
        identity=identity,
        user_id=request.user_id,
        query_text=request.message_text,
    )
    relationship_context = await load_relationship_context(
        target=relationship_target,
    )
    person_profile = await load_person_profile_for_prompt(
        identity=identity,
        user_id=request.user_id,
    )
    allowed_tools = tuple(ai_tool_service.list_allowed_tools(tool_policy))
    initiative_bias = await resolve_initiative_bias(
        relationship_target=relationship_target,
    )
    return ReplyInputs(
        turns=turns,
        conversation_summary=conversation_summary,
        relationship_target=relationship_target,
        model_target=model_target,
        tool_policy=tool_policy,
        persona=persona,
        recalled_memories=recalled_memories,
        relationship_context=relationship_context,
        person_profile=person_profile,
        allowed_tools=allowed_tools,
        initiative_bias=initiative_bias,
    )


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
    selected = await model_gateway.select_model(
        query=AIModelRouteQuery(task_class=pre_tool_task_class),
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
    response = await _safe_generate(
        _GenerationRequest(
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
    delivery_result = await _deliver_generated_reply(
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
    post_tool_task_class: str | None = None

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
            roleplay_selected = await model_gateway.select_model(
                query=AIModelRouteQuery(task_class=post_tool_task_class),
                target=build_model_binding_target(
                    request.identity,
                    request.user_id,
                ),
            )
            refinement = await _safe_generate(
                _GenerationRequest(
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
    delivery_result = await _deliver_generated_reply(
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


async def _deliver_generated_reply(
    request: "AIRuntimeReplyRequest",
    reply_text: str,
) -> DeliveryOutcome | None:
    """Deliver a proactive reply for future_task mode via NoneBot native API."""
    if request.runtime_mode != "future_task" or not reply_text.strip():
        return None

    import nonebot

    identity = request.identity
    bot = nonebot.get_bots().get(identity.bot_id)
    if bot is None:
        return DeliveryOutcome(delivered=False, error="bot_not_connected")

    try:
        if identity.scene_type == "group":
            await bot.call_api(
                "send_group_msg",
                group_id=int(identity.scene_id),
                message=reply_text,
            )
        else:
            await bot.call_api(
                "send_private_msg",
                user_id=int(identity.scene_id),
                message=reply_text,
            )
    except Exception as exc:  # noqa: BLE001
        return DeliveryOutcome(delivered=False, error=str(exc))
    return DeliveryOutcome(delivered=True)


async def _safe_generate(
    request: _GenerationRequest,
) -> "AIModelGenerateResponse | None":
    try:
        return await model_gateway.generate_native(
            selected=request.selected,
            prompt=request.prompt,
            tools=request.tools,
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).warning(
            "AI trace {} {} for session {}",
            request.trace_id,
            request.failure_stage,
            request.session_id,
        )
        return None
