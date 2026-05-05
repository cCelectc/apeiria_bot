"""Native runtime planning for AI session turns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.config import get_ai_plugin_config
from apeiria.ai.prompting import (
    project_reply_prompt_regions,
    prompt_region_diagnostics,
    render_messages,
)
from apeiria.ai.skills import ai_skill_service
from apeiria.ai.tools import (
    ToolGatewayRequest,
    ToolGatewayResult,
    tool_gateway,
)
from apeiria.app.ai.pipeline.composer import (
    AIRuntimeComposeInput,
    build_pre_tool_reply_packet,
)
from apeiria.app.ai.pipeline.model_steps import (
    build_no_model_diagnostic,
    select_pipeline_fallback_models,
    select_pipeline_model,
)
from apeiria.app.ai.pipeline.routing import select_pre_tool_reply_task_class
from apeiria.app.ai.reply_strategy import summarize_reply_strategy_decision
from apeiria.app.ai.session_runtime.stages import (
    RuntimePlanningInput,
    RuntimeTurnPlan,
)
from apeiria.app.ai.session_runtime.tools import ToolOrchestrator

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelMessage
    from apeiria.ai.prompting import PromptPacket
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.app.ai.pipeline.input_steps import ReplyInputs
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.app.ai.reply_strategy import ReplyStrategyDecision


@dataclass(frozen=True)
class RuntimePromptPlanningInput:
    """Prompt-facing runtime planning materials for reply prompt projection."""

    skill_runtime: ToolGatewayResult
    skill_activation: str | None
    has_tools: bool | None = None


async def plan_runtime_turn(
    *,
    planning_input: RuntimePlanningInput,
) -> RuntimeTurnPlan | None:
    """Resolve the runtime-owned model, prompt, and tool plan for one turn."""

    request = planning_input.request
    inputs = planning_input.inputs
    social_decision = planning_input.social_decision
    current_time = planning_input.current_time
    trace_id = planning_input.trace_id

    identity = request.identity
    tool_execution_timeout_seconds = (
        get_ai_plugin_config().tool_execution_timeout_seconds
    )
    allowed_tool_specs = (
        () if social_decision.tool_mode == "avoid" else tuple(inputs.allowed_tools)
    )
    tool_exposure_plan = ToolOrchestrator().plan_exposure(
        allowed_tools=allowed_tool_specs,
        policy=inputs.tool_policy,
        ordinary_ambient_group=(
            identity.scene_type == "group"
            and not request.is_tome
            and request.runtime_mode != "future_task"
        ),
        execution_timeout_seconds=tool_execution_timeout_seconds,
        current_time=current_time,
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
        has_tools=tool_exposure_plan.has_executable_tools,
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
    prompt_input = RuntimePromptPlanningInput(
        skill_runtime=skill_runtime,
        skill_activation=skill_selection.activation_prompt,
        has_tools=tool_exposure_plan.has_executable_tools,
    )
    prompt_packet = build_initial_runtime_reply_prompt_packet(
        request=request,
        inputs=inputs,
        social_decision=social_decision,
        prompt_input=prompt_input,
    )
    prompt_diagnostics = prompt_region_diagnostics(
        project_reply_prompt_regions(prompt_packet)
    )
    return RuntimeTurnPlan(
        stage="planning",
        selected=selected,
        fallback_models=await select_pipeline_fallback_models(selected),
        skill_runtime=skill_runtime,
        skill_activation=skill_selection.activation_prompt,
        pre_tool_task_class=pre_tool_task_class,
        prompt_messages=render_messages(prompt_packet),
        prompt_diagnostics=prompt_diagnostics,
        tool_exposure_plan=tool_exposure_plan,
        reply_compose_input=_initial_reply_compose_input(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prompt_input=prompt_input,
        ),
        prompt_packet=prompt_packet,
        tool_mode=social_decision.tool_mode,
        tool_execution_timeout_seconds=tool_execution_timeout_seconds,
    )


def build_initial_runtime_reply_prompt_messages(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: "ReplyInputs",
    social_decision: "ReplyStrategyDecision",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> tuple["AIModelMessage", ...]:
    """Build the first model prompt messages used by direct/tool planning."""

    return render_messages(
        build_initial_runtime_reply_prompt_packet(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prompt_input=prompt_input,
        )
    )


def build_initial_runtime_reply_prompt_packet(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: "ReplyInputs",
    social_decision: "ReplyStrategyDecision",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> "PromptPacket":
    """Build the first model prompt packet used by runtime and preview planning."""

    return build_pre_tool_reply_packet(
        _initial_reply_compose_input(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prompt_input=prompt_input,
        ),
        has_tools=_initial_reply_has_tools(prompt_input),
    )


def build_initial_runtime_reply_prompt_diagnostics(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: "ReplyInputs",
    social_decision: "ReplyStrategyDecision",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> dict[str, object]:
    """Build bounded prompt-region diagnostics for the first reply prompt."""

    packet = build_initial_runtime_reply_prompt_packet(
        request=request,
        inputs=inputs,
        social_decision=social_decision,
        prompt_input=prompt_input,
    )
    return prompt_region_diagnostics(project_reply_prompt_regions(packet))


def _initial_reply_compose_input(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: "ReplyInputs",
    social_decision: "ReplyStrategyDecision",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> AIRuntimeComposeInput:
    return _build_compose_input(
        request=request,
        inputs=inputs,
        social_decision=social_decision,
        skill_runtime=prompt_input.skill_runtime,
        skill_activation=prompt_input.skill_activation,
    )


def _initial_reply_has_tools(
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> bool:
    if isinstance(prompt_input, RuntimePromptPlanningInput):
        return bool(prompt_input.has_tools)
    return prompt_input.has_executable_tools


def _build_compose_input(
    *,
    request: "AIRuntimeReplyRequest",
    inputs: "ReplyInputs",
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


__all__ = [
    "RuntimePlanningInput",
    "RuntimePromptPlanningInput",
    "build_initial_runtime_reply_prompt_diagnostics",
    "build_initial_runtime_reply_prompt_messages",
    "build_initial_runtime_reply_prompt_packet",
    "plan_runtime_turn",
]
