"""Pure helpers for selecting source-backed model profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.model.models import AIModelProfileDefinition

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apeiria.ai.model.models import AIModelRouteQuery
    from apeiria.ai.model.source_models import AISourceModelDefinition
    from apeiria.ai.model.sources import AISourceCapabilityType, AISourceDefinition


@dataclass(frozen=True)
class AISelectedModel:
    """Resolved source + profile pair ready for execution."""

    source: "AISourceDefinition"
    profile: "AIModelProfileDefinition"
    resolved_model_name: str | None = None


@dataclass(frozen=True)
class AISelectedCapabilityModel:
    """Resolved source + model pair for one non-profile capability lane."""

    capability_type: "AISourceCapabilityType"
    source: "AISourceDefinition"
    model: "AISourceModelDefinition"


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
