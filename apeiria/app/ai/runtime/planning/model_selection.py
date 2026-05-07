"""Model-selection planning boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.model import AIModelRouteQuery, model_gateway
from apeiria.app.ai.agent_turn import (
    AgentModelGenerationRequest,
    AgentModelGenerationResult,
    AgentTurnModelRuntime,
)

if TYPE_CHECKING:
    from apeiria.ai.model import (
        AIModelBindingTarget,
        AIModelGenerateResponse,
        AIModelMessage,
        AIModelTaskClass,
        AIModelToolDefinition,
        AISelectedModel,
    )


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


async def select_model(
    *,
    task_class: "AIModelTaskClass",
    target: "AIModelBindingTarget",
) -> "AISelectedModel | None":
    """Select the primary model for a runtime planning task class."""

    return await model_gateway.select_model(
        query=AIModelRouteQuery(task_class=task_class),
        target=target,
    )


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

    runtime = AgentTurnModelRuntime(model_gateway=model_gateway)
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

    from apeiria.ai.model.catalog.chat import ai_chat_model_service
    from apeiria.ai.model.routing import resolve_source_selected_model_with_fallback
    from apeiria.ai.model.routing.profile import ai_model_profile_service
    from apeiria.ai.model.sources.service import ai_source_service

    profiles = await ai_model_profile_service.list_profiles()
    enabled_profiles = {
        profile.profile_id: profile for profile in profiles if profile.enabled
    }
    sources = await ai_source_service.list_sources()
    source_models = await ai_chat_model_service.list_all_models()

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
    "build_no_model_diagnostic",
    "generate_model_turn",
    "safe_generate_model",
    "select_fallback_models",
    "select_model",
]
