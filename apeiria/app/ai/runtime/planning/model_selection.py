"""Model-selection planning boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from nonebot.log import logger

from apeiria.ai.model import AIModelRouteQuery
from apeiria.app.ai.agent_turn import (
    AgentModelGenerationRequest,
    AgentModelGenerationResult,
    AgentTurnModelRuntime,
)
from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from apeiria.ai.model import (
        AIModelBindingTarget,
        AIModelGenerateResponse,
        AIModelMessage,
        AIModelTaskClass,
        AIModelToolDefinition,
        AISelectedModel,
    )
    from apeiria.ai.model.runtime.capabilities import AIModelCallOptions


@dataclass(frozen=True)
class GenerationRequest:
    """One model generation request with trace metadata."""

    selected: "AISelectedModel"
    trace_id: str
    session_id: str
    tools: tuple["AIModelToolDefinition", ...]
    failure_stage: str
    runtime_mode: str = "message"
    response_source: str = "direct"
    messages: tuple["AIModelMessage", ...] = ()
    fallback_models: tuple["AISelectedModel", ...] = ()
    prompt: str = ""
    stream_policy: Literal["none", "optional", "required"] = "none"
    stream_sink: Any | None = None
    reasoning_options: "AIModelCallOptions | None" = None


@dataclass(frozen=True)
class RuntimeModelSelection:
    """Selected model plus runtime fallback candidates for a task."""

    selected: "AISelectedModel"
    fallback_models: tuple["AISelectedModel", ...] = ()
    routing_diagnostics: dict[str, object] = field(default_factory=dict)


async def select_model_attempt_plan(
    *,
    task_class: "AIModelTaskClass",
    target: "AIModelBindingTarget",
) -> RuntimeModelSelection | None:
    """Select a route-aware model attempt plan for a runtime task class."""

    plan = await ai_wiring.model.route_service.resolve_attempt_plan(
        AIModelRouteQuery(task_class=task_class),
        target=target,
    )
    if plan is None:
        return None
    fallback_models = plan.fallback_models
    routing_diagnostics = dict(plan.routing_diagnostics)
    if plan.route is None:
        fallback_models = await select_fallback_models(plan.selected)
        routing_diagnostics["fallback_model_count"] = len(fallback_models)
    return RuntimeModelSelection(
        selected=plan.selected,
        fallback_models=fallback_models,
        routing_diagnostics=routing_diagnostics,
    )


async def select_task_model(
    *,
    task_class: "AIModelTaskClass",
    target: "AIModelBindingTarget | None" = None,
) -> "AISelectedModel | None":
    """Select only the primary model through the route-aware boundary."""

    plan = await ai_wiring.model.route_service.resolve_attempt_plan(
        AIModelRouteQuery(task_class=task_class),
        target=target,
    )
    return None if plan is None else plan.selected


async def has_selectable_task_model(
    *,
    task_class: "AIModelTaskClass",
    target: "AIModelBindingTarget | None" = None,
) -> bool:
    """Return whether the requested task class currently resolves a model."""

    return await select_task_model(task_class=task_class, target=target) is not None


def build_no_model_diagnostic(
    *,
    trace_id: str,
    session_id: str,
    task_class: "AIModelTaskClass",
) -> str:
    """Build a bounded no-model diagnostic string."""

    return (
        f"AI trace {trace_id} skipped reply: no model selected for {task_class} "
        f"in session {session_id}"
    )


async def safe_generate_model(
    request: GenerationRequest,
) -> "AIModelGenerateResponse | None":
    """Generate a model response and log bounded failure diagnostics."""

    result = await generate_model_turn(request)
    if result.response is None:
        logger.warning(
            "AI trace {} {} for session {} finish_reason={} diagnostic={}",
            request.trace_id,
            request.failure_stage,
            request.session_id,
            result.turn.finish_reason,
            result.turn.diagnostic,
        )
    return result.response


async def generate_model_turn(
    request: GenerationRequest,
) -> AgentModelGenerationResult:
    """Generate a model response and keep the turn attempt record."""

    runtime = AgentTurnModelRuntime()
    return await runtime.generate(
        AgentModelGenerationRequest(
            trace_id=request.trace_id,
            session_id=request.session_id,
            runtime_mode=request.runtime_mode,
            selected=request.selected,
            prompt=request.prompt,
            messages=request.messages,
            tools=request.tools,
            response_source=request.response_source,
            fallback_models=request.fallback_models,
            stream_policy=request.stream_policy,
            stream_sink=request.stream_sink,
            reasoning_options=request.reasoning_options,
        )
    )


async def select_fallback_models(
    selected: "AISelectedModel",
    *,
    limit: int = 1,
) -> tuple["AISelectedModel", ...]:
    """Resolve bounded runtime fallback candidates from the profile chain."""

    if limit <= 0 or selected.profile.fallback_profile_id is None:
        return ()

    from apeiria.ai.model.routing import resolve_source_selected_model_with_fallback

    profiles = await ai_wiring.model.profile_service.list_profiles()
    enabled_profiles = {
        profile.profile_id: profile for profile in profiles if profile.enabled
    }
    sources = await ai_wiring.model.source_service.list_sources()
    source_models = await ai_wiring.model.chat_model_service.list_all_models()

    fallback_models: list[AISelectedModel] = []
    visited = {selected.profile.profile_id}
    next_profile_id = selected.profile.fallback_profile_id
    selected_key = (selected.source.source_id, selected.resolved_model_name)

    while next_profile_id and next_profile_id not in visited:
        visited.add(next_profile_id)
        profile = enabled_profiles.get(next_profile_id)
        if profile is None:
            break

        candidate = resolve_source_selected_model_with_fallback(
            sources,
            source_models,
            profiles,
            [profile],
        )
        if candidate is not None:
            candidate_key = (candidate.source.source_id, candidate.resolved_model_name)
            if candidate_key != selected_key:
                fallback_models.append(candidate)
                if len(fallback_models) >= limit:
                    break
            next_profile_id = candidate.profile.fallback_profile_id
        else:
            next_profile_id = profile.fallback_profile_id

    return tuple(fallback_models)


__all__ = [
    "GenerationRequest",
    "RuntimeModelSelection",
    "build_no_model_diagnostic",
    "generate_model_turn",
    "has_selectable_task_model",
    "safe_generate_model",
    "select_fallback_models",
    "select_model_attempt_plan",
    "select_task_model",
]
