"""Pure helpers for selecting provider and profile bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.model.models import AIModelProfileDefinition
    from apeiria.app.ai.model.providers import AIProviderDefinition


@dataclass(frozen=True)
class AISelectedModel:
    """Resolved provider + profile pair ready for execution."""

    provider: "AIProviderDefinition"
    profile: "AIModelProfileDefinition"


def select_provider_for_profile(
    providers: list["AIProviderDefinition"],
    profile: "AIModelProfileDefinition",
) -> "AIProviderDefinition | None":
    """Resolve the provider referenced by a model profile."""

    for provider in providers:
        if provider.provider_id == profile.provider_id and provider.enabled:
            return provider
    return None


def resolve_selected_model_with_fallback(
    providers: list["AIProviderDefinition"],
    profiles: list["AIModelProfileDefinition"],
    primary_profiles: list["AIModelProfileDefinition"],
) -> AISelectedModel | None:
    """Resolve the first provider-reachable profile through fallback chains."""

    enabled_profile_map = {
        profile.profile_id: profile for profile in profiles if profile.enabled
    }

    for primary in primary_profiles:
        current = primary
        visited: set[str] = set()
        while current.profile_id not in visited:
            visited.add(current.profile_id)
            provider = select_provider_for_profile(providers, current)
            if provider is not None:
                return AISelectedModel(provider=provider, profile=current)
            fallback_profile_id = current.fallback_profile_id
            if fallback_profile_id is None:
                break
            fallback_profile = enabled_profile_map.get(fallback_profile_id)
            if fallback_profile is None:
                break
            current = fallback_profile
    return None
