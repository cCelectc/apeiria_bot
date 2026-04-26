"""App-owned AI tool registration."""

from __future__ import annotations

_APP_AI_TOOLS_LOADED = False


def ensure_app_ai_tools_loaded() -> None:
    """Import app-owned AI tool handlers once so decorators can register them."""

    global _APP_AI_TOOLS_LOADED  # noqa: PLW0603
    if _APP_AI_TOOLS_LOADED:
        return

    from apeiria.ai.tools import ai_tool_service
    from apeiria.app.ai.future_task import tool_handler  # noqa: F401

    ai_tool_service.registry.register_pending_tools()
    _APP_AI_TOOLS_LOADED = True
