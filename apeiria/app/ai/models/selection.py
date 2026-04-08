"""Pure helpers for selecting provider and profile bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.models.models import AIModelProfileDefinition
    from apeiria.app.ai.providers.models import AIProviderDefinition


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
