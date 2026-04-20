"""Pure helpers for model profile routing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.ai.model.models import (
        AIModelProfileDefinition,
        AIModelRouteQuery,
    )


def list_model_profile_candidates(
    profiles: list["AIModelProfileDefinition"],
    query: "AIModelRouteQuery",
) -> list["AIModelProfileDefinition"]:
    """Return enabled task-matched profiles in routing order."""

    candidates = [
        profile
        for profile in profiles
        if profile.enabled and profile.task_class == query.task_class
    ]
    return sorted(candidates, key=lambda item: item.priority)


def resolve_model_profile(
    profiles: list["AIModelProfileDefinition"],
    query: "AIModelRouteQuery",
) -> "AIModelProfileDefinition | None":
    """Resolve the highest-priority enabled profile for a task class."""

    candidates = list_model_profile_candidates(profiles, query)
    if not candidates:
        return None
    return candidates[0]
