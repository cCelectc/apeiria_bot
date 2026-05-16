"""Native runtime planning for AI session turns."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.config import get_ai_plugin_config
from apeiria.ai.prompting import render_messages
from apeiria.ai.tools import (
    ai_tool_service,
    summarize_tool_policy,
)
from apeiria.app.ai.runtime.context.projection import (
    project_runtime_context,
)
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
from apeiria.app.ai.runtime.multimodal import project_media_into_messages
from apeiria.app.ai.runtime.planning.diagnostics import (
    build_prompt_region_diagnostics,
)
from apeiria.app.ai.runtime.planning.model_selection import (
    build_no_model_diagnostic,
    select_fallback_models,
    select_model,
)
from apeiria.app.ai.runtime.planning.prompts import (
    RuntimePromptPlanningInput,
    build_pre_tool_reply_packet,
    compose_input_from_context_projection,
)
from apeiria.app.ai.runtime.planning.reply_decision import (
    select_pre_tool_reply_task_class,
)
from apeiria.app.ai.runtime.planning.skills import select_runtime_skills
from apeiria.app.ai.runtime.planning.tool_exposure import (
    ToolOrchestrator,
    build_tool_guidance_text,
    compile_tool_exposure_provider_schema,
)
from apeiria.app.ai.runtime.stages import (
    RuntimePlanningInput,
    RuntimeTurnPlan,
)

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelMessage
    from apeiria.ai.prompting import PromptPacket
    from apeiria.app.ai.runtime.planning.prompts import RuntimePromptComposeInput
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
    tool_orchestrator = ToolOrchestrator()
    initial_tool_exposure_plan = tool_orchestrator.plan_exposure(
        allowed_tools=allowed_tool_specs,
        policy=context.tool_policy,
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
        policy=context.tool_policy,
        execution_timeout_seconds=tool_execution_timeout_seconds,
        current_time=current_time,
        model_supports_tools=selected.resolved_capabilities.supports_tool_calling,
    )

    tool_runtime = RuntimeToolLoopResult(
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
    context_projection = project_runtime_context(
        turn=turn,
        context=context,
        tool_runtime=tool_runtime,
        skill_activation=skill_selection.activation_prompt,
        projection_mode="runtime",
    )
    reply_compose_input = compose_input_from_context_projection(
        context_projection.prompt,
    )
    reply_compose_input = replace(
        reply_compose_input,
        tool_guidance=build_tool_guidance_text(tool_exposure_plan),
    )
    prompt_packet = build_pre_tool_reply_packet(
        reply_compose_input,
        has_tools=tool_exposure_plan.has_executable_tools,
    )
    prompt_messages, media_diagnostics = project_media_into_messages(
        render_messages(prompt_packet),
        source=turn.source,
    )
    prompt_diagnostics = build_prompt_region_diagnostics(prompt_packet)
    prompt_diagnostics = {
        **prompt_diagnostics,
        "context": _context_diagnostics_summary(
            context_projection.diagnostics.as_dict()
        ),
        "tool_exposure": _tool_exposure_diagnostics_summary(
            tool_exposure_plan.diagnostics
        ),
        "rag": _rag_diagnostics_summary(context_projection.diagnostics.as_dict()),
    }
    if media_diagnostics:
        prompt_diagnostics = {**prompt_diagnostics, **media_diagnostics}
    if turn.source.speech_diagnostics:
        prompt_diagnostics = {
            **prompt_diagnostics,
            "speech": list(turn.source.speech_diagnostics),
        }
    return RuntimeTurnPlan(
        stage="planning",
        selected=selected,
        fallback_models=await select_fallback_models(selected),
        tool_runtime=tool_runtime,
        skill_activation=skill_selection.activation_prompt,
        pre_tool_task_class=pre_tool_task_class,
        prompt_messages=prompt_messages,
        prompt_diagnostics=prompt_diagnostics,
        context_projection_diagnostics=context_projection.diagnostics.as_dict(),
        tool_exposure_plan=tool_exposure_plan,
        reply_compose_input=reply_compose_input,
        prompt_packet=prompt_packet,
        tool_mode=social_decision.tool_mode,
        tool_execution_timeout_seconds=tool_execution_timeout_seconds,
    )


def build_initial_runtime_reply_prompt_messages(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> tuple["AIModelMessage", ...]:
    """Build the first model prompt messages used by direct/tool planning."""

    messages = render_messages(
        build_initial_runtime_reply_prompt_packet(
            turn=turn,
            context=context,
            prompt_input=prompt_input,
        )
    )
    projected, _diagnostics = project_media_into_messages(messages, source=turn.source)
    return projected


def build_initial_runtime_reply_prompt_packet(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> "PromptPacket":
    """Build the first model prompt packet used by runtime and preview planning."""

    return build_pre_tool_reply_packet(
        build_initial_prompt_compose_input(
            turn=turn,
            context=context,
            prompt_input=prompt_input,
        ),
        has_tools=_initial_reply_has_tools(prompt_input),
    )


def build_initial_runtime_reply_prompt_diagnostics(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> dict[str, object]:
    """Build bounded prompt-region diagnostics for the first reply prompt."""

    packet = build_initial_runtime_reply_prompt_packet(
        turn=turn,
        context=context,
        prompt_input=prompt_input,
    )
    return build_prompt_region_diagnostics(packet)


def build_initial_prompt_compose_input(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> "RuntimePromptComposeInput":
    context_projection = project_runtime_context(
        turn=turn,
        context=context,
        tool_runtime=prompt_input.tool_runtime,
        skill_activation=prompt_input.skill_activation,
        projection_mode="runtime",
    )
    compose_input = compose_input_from_context_projection(context_projection.prompt)
    if isinstance(prompt_input, RuntimeTurnPlan):
        return replace(
            compose_input,
            tool_guidance=build_tool_guidance_text(prompt_input.tool_exposure_plan),
        )
    return compose_input


def _initial_reply_has_tools(
    prompt_input: RuntimeTurnPlan | RuntimePromptPlanningInput,
) -> bool:
    if isinstance(prompt_input, RuntimePromptPlanningInput):
        return bool(prompt_input.has_tools)
    return prompt_input.has_executable_tools


def _context_diagnostics_summary(
    diagnostics: dict[str, object],
) -> dict[str, object]:
    keys = (
        "projection_mode",
        "turn_count",
        "recalled_memory_count",
        "memory_layers",
        "memory_layer_counts",
        "memory_use_mode_counts",
        "memory_lifecycle_counts",
        "memory_selected",
        "memory_excluded",
        "profile_card_line_count",
        "has_relationship_context",
        "has_conversation_summary",
        "allowed_capability_count",
    )
    return {key: diagnostics[key] for key in keys if key in diagnostics}


def _tool_exposure_diagnostics_summary(
    diagnostics: dict[str, object],
) -> dict[str, object]:
    keys = (
        "selected_tool_count",
        "execution_timeout_seconds",
        "parallel_safe_tool_names",
        "read_only_tool_names",
        "mutating_tool_names",
        "approval_required_tool_names",
        "tool_required_levels",
        "tool_timeout_seconds",
        "capability_contract_count",
        "capability_visible_tool_count",
        "capability_hidden_count",
        "capability_denied_count",
        "capability_unavailable_count",
        "model_supports_tools",
    )
    return {key: diagnostics[key] for key in keys if key in diagnostics}


def _rag_diagnostics_summary(
    diagnostics: dict[str, object],
) -> dict[str, object]:
    keys = (
        "rag_enabled",
        "rag_selected_count",
        "rag_candidate_count",
        "rag_missing_embedding_count",
        "rag_stale_embedding_count",
        "rag_rerank_status",
        "rag_degradation_reason",
    )
    return {
        key.removeprefix("rag_"): diagnostics[key] for key in keys if key in diagnostics
    }


__all__ = [
    "RuntimePlanningInput",
    "RuntimePromptPlanningInput",
    "build_initial_prompt_compose_input",
    "build_initial_runtime_reply_prompt_diagnostics",
    "build_initial_runtime_reply_prompt_messages",
    "build_initial_runtime_reply_prompt_packet",
    "plan_runtime_turn",
]
