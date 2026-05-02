"""App-owned AI tool registration primitives."""

from __future__ import annotations

_APP_AI_TOOL_MODULES_LOADED = False


def load_app_ai_tool_modules() -> None:
    """Import app-owned AI tool handlers once so decorators can collect specs."""

    global _APP_AI_TOOL_MODULES_LOADED  # noqa: PLW0603
    if _APP_AI_TOOL_MODULES_LOADED:
        return

    from apeiria.app.ai.future_task import tool_handler  # noqa: F401

    _APP_AI_TOOL_MODULES_LOADED = True


def drain_pending_ai_tools() -> int:
    """Register pending decorator-collected AI tool specs."""

    from apeiria.ai.tools import ai_tool_service

    return ai_tool_service.registry.register_pending_tools()


def ensure_app_ai_tools_loaded() -> None:
    """Compatibility helper for isolated tests and older internal callers."""

    load_app_ai_tool_modules()
    drain_pending_ai_tools()
