"""Plugin-facing AI registration helpers."""

from __future__ import annotations

import inspect
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from apeiria.ai.contributions import ai_contributions
from apeiria.ai.tools.decorators import ai_tool as define_ai_tool
from apeiria.ai.tools.models import AIToolLevel

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from apeiria.ai.tools.models import AIToolDefinition, AIToolResult

    AIToolHandler = Callable[..., Awaitable[AIToolResult]]


_live_platform_context: ContextVar[Any | None] = ContextVar(
    "apeiria_live_platform_context",
    default=None,
)


def _get_live_platform_context() -> Any | None:
    return _live_platform_context.get()


def ai_tool(
    *,
    name: str,
    description: str,
    required_level: AIToolLevel | str = AIToolLevel.READ,
) -> "Callable[[AIToolHandler], AIToolHandler]":
    """Declare a plugin-owned local executable AI tool."""

    def decorator(func: "AIToolHandler") -> "AIToolHandler":
        decorated = define_ai_tool(
            name=name,
            description=description,
            required_level=required_level,
            origin="plugin",
            manageable=True,
        )(func)
        func_with_metadata = cast("Any", func)
        tool = cast("AIToolDefinition", func_with_metadata.__ai_tool_definition__)
        ai_contributions.register_tool(tool=tool)
        return cast("AIToolHandler", decorated)

    return decorator


def ai_skill_source(
    path: str | Path,
    *,
    base_path: str | Path | None = None,
) -> Path:
    """Declare a plugin-owned AI skill directory or ``SKILL.md`` file."""

    resolved_base = _caller_directory() if base_path is None else base_path
    return ai_contributions.register_skill_source(
        path,
        base_path=resolved_base,
    ).path


def live_platform_context() -> Any | None:
    """Return the current live platform context for this AI tool turn."""

    return _get_live_platform_context()


def _caller_directory() -> Path:
    frame = inspect.currentframe()
    if frame is None:
        return Path.cwd()
    helper_frame = frame.f_back
    caller_frame = helper_frame.f_back if helper_frame is not None else None
    caller_file = (
        caller_frame.f_globals.get("__file__") if caller_frame is not None else None
    )
    if caller_file is None:
        return Path.cwd()
    return Path(str(caller_file)).resolve(strict=False).parent


__all__ = ["ai_skill_source", "ai_tool", "live_platform_context"]
