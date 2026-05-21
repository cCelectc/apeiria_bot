"""Pure helpers for selecting source-backed model profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import TYPE_CHECKING

from apeiria.ai.model.routing.models import (
    AIModelProfileDefinition,
    AIModelRouteDefinition,
    AIModelRouteMemberDefinition,
)
from apeiria.ai.model.runtime.capabilities import (
    AIModelCapabilities,
    merge_model_capabilities,
    parse_model_capabilities,
)
from apeiria.ai.model.sources.models import resolve_adapter_kind_for_client_type

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apeiria.ai.model.catalog.models import AISourceModelDefinition
    from apeiria.ai.model.routing.models import AIModelRouteQuery
    from apeiria.ai.model.sources.models import (
        AISourceCapabilityType,
        AISourceDefinition,
    )


@dataclass(frozen=True)
class AISelectedModel:
    """Resolved source + profile pair ready for execution."""

    source: "AISourceDefinition"
    profile: "AIModelProfileDefinition"
    resolved_model_name: str | None = None
    source_model: "AISourceModelDefinition | None" = None
    resolved_capabilities: AIModelCapabilities = field(
        default_factory=AIModelCapabilities
    )
    model_default_options: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AISelectedCapabilityModel:
    """Resolved source + model pair for one non-profile capability lane."""

    capability_type: "AISourceCapabilityType"
    source: "AISourceDefinition"
    model: "AISourceModelDefinition"


@dataclass(frozen=True)
class AIModelAttemptPlan:
    """Resolved model route attempt sequence for one turn."""

    route: AIModelRouteDefinition | None
    selected: AISelectedModel
    fallback_models: tuple[AISelectedModel, ...] = ()


def select_source_for_profile(
    sources: "Sequence[AISourceDefinition]",
    source_id: str,
) -> "AISourceDefinition | None":
    """Resolve the enabled source that owns one concrete chat model."""

    return next(
        (item for item in sources if item.source_id == source_id and item.enabled),
        None,
    )


def resolve_source_selected_model_with_fallback(
    sources: "Sequence[AISourceDefinition]",
    source_models: "Sequence[AISourceModelDefinition]",
    profiles: "Sequence[AIModelProfileDefinition]",
    primary_profiles: "Sequence[AIModelProfileDefinition]",
) -> AISelectedModel | None:
    """Resolve the first source-backed model through fallback chains."""

    enabled_profile_map = {
        profile.profile_id: profile for profile in profiles if profile.enabled
    }
    models_by_id = {model.model_id: model for model in source_models if model.enabled}

    for primary in primary_profiles:
        current = primary
        visited: set[str] = set()
        while current.profile_id not in visited:
            visited.add(current.profile_id)
            selected = _resolve_source_selected_model(
                sources=sources,
                models_by_id=models_by_id,
                profile=current,
            )
            if selected is not None:
                return selected
            fallback_profile_id = current.fallback_profile_id
            if fallback_profile_id is None:
                break
            fallback_profile = enabled_profile_map.get(fallback_profile_id)
            if fallback_profile is None:
                break
            current = fallback_profile
    return None


def resolve_source_selected_model(
    sources: "Sequence[AISourceDefinition]",
    source_models: "Sequence[AISourceModelDefinition]",
    profile: AIModelProfileDefinition,
) -> AISelectedModel | None:
    """Resolve one source-backed profile without following fallback links."""

    models_by_id = {model.model_id: model for model in source_models if model.enabled}
    return _resolve_source_selected_model(
        sources=sources,
        models_by_id=models_by_id,
        profile=profile,
    )


def resolve_model_route_attempt_plan(  # noqa: PLR0913
    route: AIModelRouteDefinition,
    members: "Sequence[AIModelRouteMemberDefinition]",
    profiles: "Sequence[AIModelProfileDefinition]",
    sources: "Sequence[AISourceDefinition]",
    source_models: "Sequence[AISourceModelDefinition]",
    *,
    randomizer: Random | None = None,
) -> AIModelAttemptPlan | None:
    """Resolve one route into a selected model and optional fallbacks."""

    if not route.enabled:
        return None
    candidate_models = _resolve_route_member_models(
        route=route,
        members=members,
        profiles=profiles,
        sources=sources,
        source_models=source_models,
    )
    if not candidate_models:
        return None
    if route.mode == "load_balance":
        selected = _select_weighted_model(candidate_models, randomizer=randomizer)
        ordered_candidates = _ordered_after_selected(candidate_models, selected)
    else:
        selected = candidate_models[0][0]
        ordered_candidates = [item[0] for item in candidate_models]

    fallback_models = tuple(
        candidate for candidate in ordered_candidates if candidate is not selected
    )
    if not route.fallback_on_failure:
        fallback_models = ()
    return AIModelAttemptPlan(
        route=route,
        selected=selected,
        fallback_models=fallback_models,
    )


def _resolve_route_member_models(
    *,
    route: AIModelRouteDefinition,
    members: "Sequence[AIModelRouteMemberDefinition]",
    profiles: "Sequence[AIModelProfileDefinition]",
    sources: "Sequence[AISourceDefinition]",
    source_models: "Sequence[AISourceModelDefinition]",
) -> list[tuple[AISelectedModel, AIModelRouteMemberDefinition]]:
    profile_map = {
        profile.profile_id: profile
        for profile in profiles
        if profile.enabled and profile.task_class == route.task_class
    }
    ordered_members = sorted(
        (
            member
            for member in members
            if member.enabled and member.route_id == route.route_id
        ),
        key=lambda item: (item.position, item.route_member_id),
    )
    selected_members: list[tuple[AISelectedModel, AIModelRouteMemberDefinition]] = []
    for member in ordered_members:
        profile = profile_map.get(member.profile_id)
        if profile is None:
            continue
        selected = resolve_source_selected_model(sources, source_models, profile)
        if selected is None:
            continue
        selected_members.append((selected, member))
    return selected_members


def _select_weighted_model(
    candidates: list[tuple[AISelectedModel, AIModelRouteMemberDefinition]],
    *,
    randomizer: Random | None,
) -> AISelectedModel:
    total_weight = sum(max(member.weight, 0) for _, member in candidates)
    if total_weight <= 0:
        return candidates[0][0]
    picker = randomizer or Random()
    point = picker.uniform(0, total_weight)
    cumulative = 0.0
    for selected, member in candidates:
        cumulative += max(member.weight, 0)
        if point <= cumulative:
            return selected
    return candidates[-1][0]


def _ordered_after_selected(
    candidates: list[tuple[AISelectedModel, AIModelRouteMemberDefinition]],
    selected: AISelectedModel,
) -> list[AISelectedModel]:
    ordered = [selected]
    ordered.extend(
        candidate for candidate, _ in candidates if candidate is not selected
    )
    return ordered


def resolve_implicit_selected_model(
    sources: "Sequence[AISourceDefinition]",
    source_models: "Sequence[AISourceModelDefinition]",
    *,
    query: "AIModelRouteQuery | None" = None,
) -> AISelectedModel | None:
    """Resolve an implicit default model when no profile routing is configured."""

    enabled_source_map = {
        source.source_id: source for source in sources if source.enabled
    }
    enabled_models = [
        model
        for model in source_models
        if model.enabled and model.source_id in enabled_source_map
    ]
    if not enabled_models:
        return None

    selected_model = next(
        (model for model in enabled_models if model.is_default),
        enabled_models[0],
    )
    task_class = query.task_class if query is not None else "reply_default"
    implicit_profile = AIModelProfileDefinition(
        profile_id=f"implicit_{task_class}",
        name=f"Implicit {task_class}",
        model_id=selected_model.model_id,
        task_class=task_class,
        priority=9999,
        enabled=True,
    )
    return AISelectedModel(
        source=enabled_source_map[selected_model.source_id],
        profile=implicit_profile,
        resolved_model_name=selected_model.model_identifier,
        source_model=selected_model,
        resolved_capabilities=_resolve_capabilities(
            source=enabled_source_map[selected_model.source_id],
            model=selected_model,
        ),
        model_default_options=dict(selected_model.default_options or {}),
    )


def _resolve_source_selected_model(
    *,
    sources: "Sequence[AISourceDefinition]",
    models_by_id: dict[str, "AISourceModelDefinition"],
    profile: "AIModelProfileDefinition",
) -> AISelectedModel | None:
    selected_model = models_by_id.get(profile.model_id)
    if selected_model is None:
        return None
    source = select_source_for_profile(sources, selected_model.source_id)
    if source is None:
        return None
    return AISelectedModel(
        source=source,
        profile=profile,
        resolved_model_name=selected_model.model_identifier,
        source_model=selected_model,
        resolved_capabilities=_resolve_capabilities(
            source=source,
            model=selected_model,
        ),
        model_default_options=dict(selected_model.default_options or {}),
    )


def resolve_capability_selected_model(
    sources: "Sequence[AISourceDefinition]",
    source_models: "Sequence[AISourceModelDefinition]",
    *,
    capability_type: "AISourceCapabilityType",
    preferred_source_id: str | None = None,
) -> AISelectedCapabilityModel | None:
    """Resolve the default enabled source/model pair for one capability type."""

    enabled_sources = [
        source
        for source in sources
        if source.enabled and source.capability_type == capability_type
    ]
    if not enabled_sources:
        return None

    source_by_id = {source.source_id: source for source in enabled_sources}
    enabled_models = [
        model
        for model in source_models
        if model.enabled and model.source_id in source_by_id
    ]
    if not enabled_models:
        return None

    if preferred_source_id:
        preferred_default = next(
            (
                model
                for model in enabled_models
                if model.source_id == preferred_source_id and model.is_default
            ),
            None,
        )
        if preferred_default is not None:
            return AISelectedCapabilityModel(
                capability_type=capability_type,
                source=source_by_id[preferred_default.source_id],
                model=preferred_default,
            )
        preferred_model = next(
            (
                model
                for model in enabled_models
                if model.source_id == preferred_source_id
            ),
            None,
        )
        if preferred_model is not None:
            return AISelectedCapabilityModel(
                capability_type=capability_type,
                source=source_by_id[preferred_model.source_id],
                model=preferred_model,
            )

    selected_model = next(
        (model for model in enabled_models if model.is_default),
        enabled_models[0],
    )
    return AISelectedCapabilityModel(
        capability_type=capability_type,
        source=source_by_id[selected_model.source_id],
        model=selected_model,
    )


def _resolve_capabilities(
    *,
    source: "AISourceDefinition",
    model: "AISourceModelDefinition",
) -> AIModelCapabilities:
    adapter_kind = source.adapter_kind or resolve_adapter_kind_for_client_type(
        source.client_type
    )
    adapter_capabilities = _default_capabilities_for_adapter(adapter_kind)
    source_capabilities = merge_model_capabilities(
        adapter_capabilities,
        parse_model_capabilities(source.capability_metadata),
    )
    return merge_model_capabilities(
        source_capabilities,
        parse_model_capabilities(model.capability_metadata),
    )


def _default_capabilities_for_adapter(adapter_kind: str | None) -> AIModelCapabilities:
    from apeiria.ai.model.runtime.registry import provider_adapter_registry

    return provider_adapter_registry.get(adapter_kind).default_capabilities
