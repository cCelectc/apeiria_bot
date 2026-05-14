"""App-owned AI tool registration primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.ai.contributions import AIContributionRegistry


def register_app_ai_tools(registry: "AIContributionRegistry") -> int:
    """Register app-owned executable AI tool declarations once."""

    from apeiria.app.ai.builtin_tools import register_internal_tools

    return register_internal_tools(registry)
