"""Tool handler modules — import triggers @ai_tool registration."""

from __future__ import annotations

_LOADED = False


def ensure_handlers_loaded() -> None:
    """Import all handler modules so their @ai_tool decorators fire."""

    global _LOADED  # noqa: PLW0603
    if _LOADED:
        return
    _LOADED = True

    from apeiria.ai.tools.handlers import (  # noqa: F401
        memory,
        relationship,
    )
