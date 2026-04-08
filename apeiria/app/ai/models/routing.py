"""Pure helpers for model profile routing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.models.models import (
        AIModelProfileDefinition,
        AIModelRouteQuery,
    )


def resolve_model_profile(
    profiles: list["AIModelProfileDefinition"],
    query: "AIModelRouteQuery",
) -> "AIModelProfileDefinition | None":
    """Resolve the highest-priority enabled profile for a task class."""

    candidates = [
        profile
        for profile in profiles
        if profile.enabled and profile.task_class == query.task_class
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.priority)[0]
