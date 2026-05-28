"""Native runtime planning for AI session turns."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.prompting import render_messages
from apeiria.ai.runtime_settings import ai_runtime_settings_service
from apeiria.ai.tools import summarize_tool_policy
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
    select_model_attempt_plan,
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
    ToolExposurePlan,
    ToolOrchestrator,
    build_tool_guidance_text,
    compile_tool_exposure_provider_schema,
)
from apeiria.app.ai.runtime.stages import (
    RuntimePlanningInput,
    RuntimePlanningOutput,
    RuntimePlanningReport,
    RuntimeTurnPlan,
)
from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import AIModelMessage, AIModelTaskClass
    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.prompting import PromptPacket
    from apeiria.ai.tools.models import AIToolDefinition
    from apeiria.app.ai.runtime.planning.prompts import RuntimePromptComposeInput
    from apeiria.app.ai.runtime.session.context import (
        RuntimeContextMaterials,
        RuntimeTurnInput,
    )


@dataclass(frozen=True, slots=True)
class RuntimeReplyPlanningSelection:
    """Shared model/tool exposure selection for runtime reply planning."""

    selected: "AISelectedModel"
    fallback_models: tuple["AISelectedModel", ...]
    routing_diagnostics: dict[str, object]
    tool_exposure_plan: ToolExposurePlan
    pre_tool_task_class: "AIModelTaskClass"

    @property
    def has_executable_tools(self) -> bool:
        return self.tool_exposure_plan.has_executable_tools


async def plan_runtime_turn(
    *,
    planning_input: RuntimePlanningInput,
) -> RuntimePlanningOutput | None:
    """Resolve the runtime-owned model, prompt, and tool plan for one turn."""

    turn = planning_input.turn
    context = planning_input.context
    social_decision = planning_input.social_decision
    current_time = planning_input.current_time
    trace_id = planning_input.trace_id

    identity = turn.identity
    tool_execution_timeout_seconds = (
        ai_runtime_settings_service.get_settings().tool_execution_timeout_seconds
    )
    allowed_tool_specs = (
        () if social_decision.tool_mode == "avoid" else tuple(context.allowed_tools)
    )
    planning_selection = await select_runtime_reply_planning(
        context=context,
        allowed_tool_specs=allowed_tool_specs,
        tool_execution_timeout_seconds=tool_execution_timeout_seconds,
        current_time=current_time,
    )
    if planning_selection is None:
        logger.debug(
            build_no_model_diagnostic(
                trace_id=trace_id,
                session_id=identity.session_id,
                task_class=select_pre_tool_reply_task_class(has_tools=False),
            )
        )
        return None
    selected = planning_selection.selected
    tool_exposure_plan = planning_selection.tool_exposure_plan
    pre_tool_task_class = planning_selection.pre_tool_task_class

    tool_runtime = RuntimeToolLoopResult(
        policy_text=summarize_tool_policy(
            ai_wiring.tool_service.registry.list_tools(),
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
    plan = RuntimeTurnPlan(
        stage="planning",
        selected=selected,
        fallback_models=planning_selection.fallback_models,
        tool_runtime=tool_runtime,
        skill_activation=skill_selection.activation_prompt,
        pre_tool_task_class=pre_tool_task_class,
        prompt_messages=prompt_messages,
        tool_exposure_plan=tool_exposure_plan,
        reply_compose_input=reply_compose_input,
        tool_mode=social_decision.tool_mode,
        tool_execution_timeout_seconds=tool_execution_timeout_seconds,
    )
    return RuntimePlanningOutput(
        plan=plan,
        report=RuntimePlanningReport(
            selected_model_ref=_selected_model_ref(plan),
            fallback_model_count=len(plan.fallback_models),
            tool_exposure_summary=_tool_exposure_summary(plan),
            prompt_diagnostics=prompt_diagnostics,
            context_projection_diagnostics=context_projection.diagnostics.as_dict(),
            routing_diagnostics=planning_selection.routing_diagnostics,
        ),
    )


async def select_runtime_reply_planning(
    *,
    context: "RuntimeContextMaterials",
    allowed_tool_specs: tuple["AIToolDefinition", ...],
    tool_execution_timeout_seconds: float | None,
    current_time: "datetime | None" = None,
) -> RuntimeReplyPlanningSelection | None:
    """Select reply model and model-aware tool exposure once for runtime/preview."""

    tool_orchestrator = ToolOrchestrator()
    initial_tool_exposure_plan = tool_orchestrator.plan_exposure(
        allowed_tools=allowed_tool_specs,
        policy=context.tool_policy,
        execution_timeout_seconds=tool_execution_timeout_seconds,
        current_time=current_time,
    )
    initial_task_class = select_pre_tool_reply_task_class(
        has_tools=initial_tool_exposure_plan.has_executable_tools,
    )
    initial_selection = await select_model_attempt_plan(
        task_class=initial_task_class,
        target=context.model_target,
    )
    if initial_selection is None:
        fallback_task_class = select_pre_tool_reply_task_class(has_tools=False)
        if fallback_task_class == initial_task_class:
            return None
        selection = await select_model_attempt_plan(
            task_class=fallback_task_class,
            target=context.model_target,
        )
        if selection is None:
            return None
        tool_exposure_plan = tool_orchestrator.plan_exposure(
            allowed_tools=allowed_tool_specs,
            policy=context.tool_policy,
            execution_timeout_seconds=tool_execution_timeout_seconds,
            current_time=current_time,
            model_supports_tools=False,
        )
        return RuntimeReplyPlanningSelection(
            selected=selection.selected,
            fallback_models=selection.fallback_models,
            routing_diagnostics=selection.routing_diagnostics,
            tool_exposure_plan=tool_exposure_plan,
            pre_tool_task_class=fallback_task_class,
        )
    initial_selected = initial_selection.selected

    tool_exposure_plan = tool_orchestrator.plan_exposure(
        allowed_tools=allowed_tool_specs,
        policy=context.tool_policy,
        execution_timeout_seconds=tool_execution_timeout_seconds,
        current_time=current_time,
        model_supports_tools=(
            initial_selected.resolved_capabilities.supports_tool_calling
        ),
    )
    final_task_class = select_pre_tool_reply_task_class(
        has_tools=tool_exposure_plan.has_executable_tools,
    )
    if final_task_class == initial_task_class:
        return RuntimeReplyPlanningSelection(
            selected=initial_selected,
            fallback_models=initial_selection.fallback_models,
            routing_diagnostics=initial_selection.routing_diagnostics,
            tool_exposure_plan=tool_exposure_plan,
            pre_tool_task_class=final_task_class,
        )

    final_selection = await select_model_attempt_plan(
        task_class=final_task_class,
        target=context.model_target,
    )
    if final_selection is None:
        return RuntimeReplyPlanningSelection(
            selected=initial_selected,
            fallback_models=initial_selection.fallback_models,
            routing_diagnostics=initial_selection.routing_diagnostics,
            tool_exposure_plan=tool_exposure_plan,
            pre_tool_task_class=initial_task_class,
        )
    return RuntimeReplyPlanningSelection(
        selected=final_selection.selected,
        fallback_models=final_selection.fallback_models,
        routing_diagnostics=final_selection.routing_diagnostics,
        tool_exposure_plan=tool_exposure_plan,
        pre_tool_task_class=final_task_class,
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


def _selected_model_ref(plan: RuntimeTurnPlan) -> str:
    model_name = plan.selected.resolved_model_name or plan.selected.profile.model_id
    return (
        f"{plan.selected.source.source_id}:"
        f"{plan.selected.profile.profile_id}:"
        f"{model_name}"
    )


def _tool_exposure_summary(plan: RuntimeTurnPlan) -> dict[str, object]:
    tool_plan = plan.tool_exposure_plan
    summary: dict[str, object] = {
        "selected_tool_count": len(tool_plan.selected_tool_names),
        "has_executable_tools": tool_plan.has_executable_tools,
    }
    allowed_tool_count = tool_plan.diagnostics.get("allowed_tool_count")
    if isinstance(allowed_tool_count, int):
        summary["allowed_tool_count"] = allowed_tool_count
    return summary


__all__ = [
    "RuntimePlanningInput",
    "RuntimePromptPlanningInput",
    "RuntimeReplyPlanningSelection",
    "build_initial_prompt_compose_input",
    "build_initial_runtime_reply_prompt_diagnostics",
    "build_initial_runtime_reply_prompt_messages",
    "build_initial_runtime_reply_prompt_packet",
    "plan_runtime_turn",
    "select_runtime_reply_planning",
]
