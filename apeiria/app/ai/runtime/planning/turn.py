"""Native runtime planning for AI session turns."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.config import get_ai_plugin_config
from apeiria.ai.prompting import render_messages
from apeiria.ai.tools import (
    ai_tool_service,
    summarize_tool_policy,
)
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
from apeiria.app.ai.runtime.planning.diagnostics import (
    build_prompt_region_diagnostics,
)
from apeiria.app.ai.runtime.planning.model_selection import (
    build_no_model_diagnostic,
    select_fallback_models,
    select_model,
)
from apeiria.app.ai.runtime.planning.prompts import (
    RuntimePromptComposeInput,
    RuntimePromptPlanningInput,
    build_pre_tool_reply_packet,
)
from apeiria.app.ai.runtime.planning.reply_decision import (
    select_pre_tool_reply_task_class,
)
from apeiria.app.ai.runtime.planning.skills import select_runtime_skills
from apeiria.app.ai.runtime.planning.social import summarize_social_decision
from apeiria.app.ai.runtime.planning.tool_exposure import (
    ToolOrchestrator,
    compile_tool_exposure_provider_schema,
)
from apeiria.app.ai.runtime.stages import (
    RuntimePlanningInput,
    RuntimeTurnPlan,
)

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelMessage
    from apeiria.ai.prompting import PromptPacket
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
    from apeiria.app.ai.runtime.session.context import (
        RuntimeContextMaterials,
        RuntimeTurnInput,
    )


async def plan_runtime_turn(
    *,
    planning_input: RuntimePlanningInput,
) -> RuntimeTurnPlan | None:
    """Resolve the runtime-owned model, prompt, and tool plan for one turn."""

    turn = planning_input.turn
    context = planning_input.context
    social_decision = planning_input.social_decision
    current_time = planning_input.current_time
    trace_id = planning_input.trace_id

    identity = turn.identity
    tool_execution_timeout_seconds = (
        get_ai_plugin_config().tool_execution_timeout_seconds
    )
    allowed_tool_specs = (
        () if social_decision.tool_mode == "avoid" else tuple(context.allowed_tools)
    )
    tool_contracts = ai_tool_service.contract_snapshot()
    tool_bindings = ai_tool_service.binding_snapshot()
    tool_orchestrator = ToolOrchestrator()
    initial_tool_exposure_plan = tool_orchestrator.plan_exposure(
        allowed_tools=allowed_tool_specs,
        contracts=tool_contracts,
        bindings=tool_bindings,
        policy=context.tool_policy,
        ordinary_ambient_group=(
            identity.scene_type == "group"
            and not turn.is_tome
            and turn.runtime_mode != "future_task"
        ),
        execution_timeout_seconds=tool_execution_timeout_seconds,
        current_time=current_time,
    )
    pre_tool_task_class = select_pre_tool_reply_task_class(
        has_tools=initial_tool_exposure_plan.has_executable_tools,
    )
    selected = await select_model(
        task_class=pre_tool_task_class,
        target=context.model_target,
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

    tool_exposure_plan = tool_orchestrator.plan_exposure(
        allowed_tools=allowed_tool_specs,
        contracts=tool_contracts,
        bindings=tool_bindings,
        policy=context.tool_policy,
        ordinary_ambient_group=(
            identity.scene_type == "group"
            and not turn.is_tome
            and turn.runtime_mode != "future_task"
        ),
        execution_timeout_seconds=tool_execution_timeout_seconds,
        current_time=current_time,
        model_supports_tools=selected.resolved_capabilities.supports_tool_calling,
    )

    skill_runtime = RuntimeToolLoopResult(
        policy_text=summarize_tool_policy(
            ai_tool_service.registry.list_tools(),
            context.tool_policy,
        ),
        result_lines=(),
        turns=(),
        available_tools=compile_tool_exposure_provider_schema(
            tool_exposure_plan,
            current_time=current_time,
        ),
        diagnostics=dict(tool_exposure_plan.diagnostics),
    )
    skill_selection = await select_runtime_skills(
        message_text=turn.message_text,
        conversation_summary=context.conversation_summary,
    )
    prompt_input = RuntimePromptPlanningInput(
        skill_runtime=skill_runtime,
        skill_activation=skill_selection.activation_prompt,
        has_tools=tool_exposure_plan.has_executable_tools,
    )
    prompt_packet = build_initial_runtime_reply_prompt_packet(
        turn=turn,
        context=context,
        social_decision=social_decision,
        prompt_input=prompt_input,
    )
    prompt_diagnostics = build_prompt_region_diagnostics(prompt_packet)
    return RuntimeTurnPlan(
        stage="planning",
        selected=selected,
        fallback_models=await select_fallback_models(selected),
        skill_runtime=skill_runtime,
        skill_activation=skill_selection.activation_prompt,
        pre_tool_task_class=pre_tool_task_class,
        prompt_messages=render_messages(prompt_packet),
        prompt_diagnostics=prompt_diagnostics,
        tool_exposure_plan=tool_exposure_plan,
        reply_compose_input=build_initial_prompt_compose_input(
            turn=turn,
            context=context,
            social_decision=social_decision,
            prompt_input=prompt_input,
        ),
        prompt_packet=prompt_packet,
        tool_mode=social_decision.tool_mode,
        tool_execution_timeout_seconds=tool_execution_timeout_seconds,
    )


def build_initial_runtime_reply_prompt_messages(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    social_decision: "ReplyStrategyDecision",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> tuple["AIModelMessage", ...]:
    """Build the first model prompt messages used by direct/tool planning."""

    return render_messages(
        build_initial_runtime_reply_prompt_packet(
            turn=turn,
            context=context,
            social_decision=social_decision,
            prompt_input=prompt_input,
        )
    )


def build_initial_runtime_reply_prompt_packet(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    social_decision: "ReplyStrategyDecision",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> "PromptPacket":
    """Build the first model prompt packet used by runtime and preview planning."""

    return build_pre_tool_reply_packet(
        build_initial_prompt_compose_input(
            turn=turn,
            context=context,
            social_decision=social_decision,
            prompt_input=prompt_input,
        ),
        has_tools=_initial_reply_has_tools(prompt_input),
    )


def build_initial_runtime_reply_prompt_diagnostics(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    social_decision: "ReplyStrategyDecision",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> dict[str, object]:
    """Build bounded prompt-region diagnostics for the first reply prompt."""

    packet = build_initial_runtime_reply_prompt_packet(
        turn=turn,
        context=context,
        social_decision=social_decision,
        prompt_input=prompt_input,
    )
    return build_prompt_region_diagnostics(packet)


def build_initial_prompt_compose_input(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    social_decision: "ReplyStrategyDecision",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> RuntimePromptComposeInput:
    return _build_compose_input(
        turn=turn,
        context=context,
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
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    social_decision: "ReplyStrategyDecision",
    skill_runtime: RuntimeToolLoopResult,
    skill_activation: str | None,
) -> RuntimePromptComposeInput:
    return RuntimePromptComposeInput(
        persona=context.persona,
        scene_type=turn.identity.scene_type,
        person_profile=context.person_profile,
        relationship=context.relationship_context,
        tool_policy=skill_runtime.policy_text,
        tool_results=skill_runtime.result_lines,
        memories=context.recalled_memories,
        conversation_summary=context.conversation_summary,
        social_policy_summary=summarize_social_decision(social_decision),
        future_task_context=_build_future_task_context(turn.future_task),
        skill_activation=skill_activation,
        turns=context.turns,
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
    "build_initial_prompt_compose_input",
    "build_initial_runtime_reply_prompt_diagnostics",
    "build_initial_runtime_reply_prompt_messages",
    "build_initial_runtime_reply_prompt_packet",
    "plan_runtime_turn",
]
