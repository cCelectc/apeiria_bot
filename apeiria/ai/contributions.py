"""Plugin-facing AI contribution declarations.

Plugins that depend on ``apeiria.builtin_plugins.ai`` can import this module at
plugin import time to declare first-class AI tools and file-based skill sources.
The declarations are stored in a narrow registry; the AI plugin lifecycle
applies them during startup.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from apeiria.ai.tools.models import (
    AIToolDefinition,
    AIToolLevel,
    AIToolReadiness,
    coerce_tool_level,
)
from apeiria.ai.tools.schema import (
    build_json_schema,
    build_parameters_from_signature,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from apeiria.ai.tools.models import AIToolResult

    AIToolHandler = Callable[..., Awaitable[AIToolResult]]


@dataclass(frozen=True)
class AIPluginToolContribution:
    """One plugin-declared local executable tool."""

    tool: AIToolDefinition


@dataclass(frozen=True)
class AIPluginSkillSource:
    """One plugin-contributed skill file or directory path."""

    path: Path


@dataclass(frozen=True)
class AIPluginContributionSnapshot:
    """Immutable snapshot consumed by the AI lifecycle coordinator."""

    tools: tuple[AIPluginToolContribution, ...] = ()
    skill_sources: tuple[AIPluginSkillSource, ...] = ()


class AIPluginContributionRegistry:
    """In-memory registry for plugin-declared AI startup contributions."""

    def __init__(self) -> None:
        self._tools: dict[str, AIPluginToolContribution] = {}
        self._skill_sources: dict[Path, AIPluginSkillSource] = {}

    def register_tool(
        self,
        *,
        tool: AIToolDefinition,
    ) -> AIPluginToolContribution:
        """Declare one local executable tool for lifecycle registration."""

        contribution = AIPluginToolContribution(tool=_as_plugin_tool(tool))
        self._tools[contribution.tool.name] = contribution
        return contribution

    def register_skill_source(
        self,
        path: str | Path,
        *,
        base_path: str | Path | None = None,
    ) -> AIPluginSkillSource:
        """Declare a skill directory or ``SKILL.md`` file.

        Relative paths are resolved against ``base_path`` when supplied, or the
        current working directory for direct registry calls. Public helper
        functions below resolve omitted ``base_path`` values against the caller
        module directory.
        """

        resolved = _resolve_path(path, base_path=base_path)
        source = AIPluginSkillSource(path=resolved)
        self._skill_sources[resolved] = source
        return source

    def snapshot(self) -> AIPluginContributionSnapshot:
        """Return deterministic declarations without mutating the registry."""

        return AIPluginContributionSnapshot(
            tools=tuple(self._tools[name] for name in sorted(self._tools)),
            skill_sources=tuple(
                self._skill_sources[path] for path in sorted(self._skill_sources)
            ),
        )


ai_plugin_contributions = AIPluginContributionRegistry()


def register_ai_tool(
    *,
    name: str,
    description: str,
    required_level: AIToolLevel | str = AIToolLevel.READ,
    tags: tuple[str, ...] = (),
) -> "Callable[[AIToolHandler], AIToolHandler]":
    """Decorator for plugin-declared local executable tools.

    The tool definition is collected for the lifecycle coordinator rather than
    being inserted directly into the runtime singleton.
    """

    def decorator(func: "AIToolHandler") -> "AIToolHandler":
        parameters = build_parameters_from_signature(func)
        tool = AIToolDefinition(
            name=name,
            description=description,
            input_schema=build_json_schema(parameters) if parameters else _EMPTY_SCHEMA,
            required_level=coerce_tool_level(required_level),
            executor=func,
            readiness=AIToolReadiness.available(),
            origin="plugin",
            manageable=True,
            tags=tags,
        )
        ai_plugin_contributions.register_tool(tool=tool)
        func_with_metadata = cast("Any", func)
        func_with_metadata.__ai_tool_definition__ = tool
        return func

    return decorator


def register_ai_skill_source(
    path: str | Path,
    *,
    base_path: str | Path | None = None,
) -> Path:
    """Register a plugin skill directory or file and return its resolved path."""

    if base_path is None:
        base_path = _caller_directory()
    return ai_plugin_contributions.register_skill_source(
        path,
        base_path=base_path,
    ).path


def _resolve_path(
    path: str | Path,
    *,
    base_path: str | Path | None,
) -> Path:
    raw = Path(path).expanduser()
    if raw.is_absolute():
        return raw.resolve(strict=False)
    base = Path.cwd() if base_path is None else Path(base_path).expanduser()
    return (base / raw).resolve(strict=False)


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


def _as_plugin_tool(tool: AIToolDefinition) -> AIToolDefinition:
    return replace(tool, origin="plugin", manageable=True)


_EMPTY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


__all__ = [
    "AIPluginContributionRegistry",
    "AIPluginContributionSnapshot",
    "AIPluginSkillSource",
    "AIPluginToolContribution",
    "ai_plugin_contributions",
    "register_ai_skill_source",
    "register_ai_tool",
]
