"""Plugin-facing AI contribution declarations.

Plugins that depend on ``apeiria.builtin_plugins.ai`` can import this module at
plugin import time to declare AI tools, file-based skill sources, and
capability bridge handlers. The declarations are stored in a narrow registry;
the AI plugin lifecycle applies them during startup.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apeiria.ai.tools.models import AIToolSpec
from apeiria.ai.tools.schema import build_parameters_from_signature

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from apeiria.ai.tools.models import AIToolResult, AIToolRiskLevel

    AICapabilityHandler = Callable[[dict[str, Any]], Any | Awaitable[Any]]
    AIToolHandler = Callable[..., Awaitable[AIToolResult]]


@dataclass(frozen=True)
class AIPluginCapabilityContribution:
    """One plugin-contributed capability bridge handler."""

    capability_name: str
    handler: "AICapabilityHandler"


@dataclass(frozen=True)
class AIPluginSkillSource:
    """One plugin-contributed skill file or directory path."""

    path: Path


@dataclass(frozen=True)
class AIPluginContributionSnapshot:
    """Immutable snapshot consumed by the AI lifecycle coordinator."""

    tools: tuple[AIToolSpec, ...] = ()
    capability_handlers: tuple[AIPluginCapabilityContribution, ...] = ()
    skill_sources: tuple[AIPluginSkillSource, ...] = ()


class AIPluginContributionRegistry:
    """In-memory registry for plugin-declared AI startup contributions."""

    def __init__(self) -> None:
        self._tools: dict[str, AIToolSpec] = {}
        self._capability_handlers: dict[str, AIPluginCapabilityContribution] = {}
        self._skill_sources: dict[Path, AIPluginSkillSource] = {}

    def register_tool(self, tool: AIToolSpec) -> AIToolSpec:
        """Declare one AI tool for lifecycle-time registration."""

        self._tools[tool.name] = tool
        return tool

    def register_capability_handler(
        self,
        capability_name: str,
        handler: "AICapabilityHandler",
    ) -> AIPluginCapabilityContribution:
        """Declare one capability bridge handler."""

        contribution = AIPluginCapabilityContribution(
            capability_name=capability_name,
            handler=handler,
        )
        self._capability_handlers[capability_name] = contribution
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
            capability_handlers=tuple(
                self._capability_handlers[name]
                for name in sorted(self._capability_handlers)
            ),
            skill_sources=tuple(
                self._skill_sources[path] for path in sorted(self._skill_sources)
            ),
        )


ai_plugin_contributions = AIPluginContributionRegistry()


def register_ai_tool(  # noqa: PLR0913
    *,
    name: str,
    description: str,
    read_only: bool,
    concurrency_safe: bool,
    risk_level: "AIToolRiskLevel" = "low",
    is_capability_bridge: bool = False,
    tags: tuple[str, ...] = (),
) -> "Callable[[AIToolHandler], AIToolHandler]":
    """Decorator for plugin-declared AI tools.

    The tool spec is collected for the lifecycle coordinator rather than being
    inserted directly into the runtime singleton.
    """

    def decorator(func: "AIToolHandler") -> "AIToolHandler":
        spec = AIToolSpec(
            name=name,
            description=description,
            read_only=read_only,
            concurrency_safe=concurrency_safe,
            risk_level=risk_level,
            is_capability_bridge=is_capability_bridge,
            parameters=build_parameters_from_signature(func),
            entrypoint=func,
            origin="plugin",
            tags=tags,
        )
        ai_plugin_contributions.register_tool(spec)
        func.__ai_tool_spec__ = spec  # type: ignore[attr-defined]
        return func

    return decorator


def register_ai_tool_spec(tool: AIToolSpec) -> AIToolSpec:
    """Register an already-built plugin tool spec."""

    if tool.origin != "plugin":
        from dataclasses import replace

        tool = replace(tool, origin="plugin")
    return ai_plugin_contributions.register_tool(tool)


def register_ai_capability_handler(
    capability_name: str,
    handler: "AICapabilityHandler",
) -> AIPluginCapabilityContribution:
    """Register a plugin capability handler for startup application."""

    return ai_plugin_contributions.register_capability_handler(
        capability_name,
        handler,
    )


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


__all__ = [
    "AIPluginCapabilityContribution",
    "AIPluginContributionRegistry",
    "AIPluginContributionSnapshot",
    "AIPluginSkillSource",
    "ai_plugin_contributions",
    "register_ai_capability_handler",
    "register_ai_skill_source",
    "register_ai_tool",
    "register_ai_tool_spec",
]
