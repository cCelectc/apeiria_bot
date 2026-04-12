"""Pure helpers for selecting source-backed model profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.model.chat_models import AIChatModelDefinition
    from apeiria.app.ai.model.models import AIModelProfileDefinition
    from apeiria.app.ai.model.sources import AISourceDefinition


@dataclass(frozen=True)
class AISelectedModel:
    """Resolved source + profile pair ready for execution."""

    source: "AISourceDefinition"
    profile: "AIModelProfileDefinition"
    resolved_model_name: str | None = None


def select_source_for_profile(
    sources: list["AISourceDefinition"],
    source_id: str,
) -> "AISourceDefinition | None":
    """Resolve the enabled source that owns one concrete chat model."""

    return next(
        (item for item in sources if item.source_id == source_id and item.enabled),
        None,
    )


def resolve_source_selected_model_with_fallback(
    sources: list["AISourceDefinition"],
    source_models: list["AIChatModelDefinition"],
    profiles: list["AIModelProfileDefinition"],
    primary_profiles: list["AIModelProfileDefinition"],
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


def _resolve_source_selected_model(
    *,
    sources: list["AISourceDefinition"],
    models_by_id: dict[str, "AIChatModelDefinition"],
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
