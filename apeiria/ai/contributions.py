"""AI startup contribution collection."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.ai.tools.models import AIToolDefinition


@dataclass(frozen=True)
class AIToolContribution:
    """One declared local executable tool."""

    tool: AIToolDefinition


@dataclass(frozen=True)
class AISkillSourceContribution:
    """One contributed skill file or directory path."""

    path: Path


@dataclass(frozen=True)
class AIContributionSnapshot:
    """Immutable snapshot consumed by the AI lifecycle coordinator."""

    tools: tuple[AIToolContribution, ...] = ()
    skill_sources: tuple[AISkillSourceContribution, ...] = ()


class AIContributionRegistry:
    """In-memory registry for AI startup contributions."""

    def __init__(self) -> None:
        self._tools: list[AIToolContribution] = []
        self._skill_sources: dict[Path, AISkillSourceContribution] = {}

    def register_tool(
        self,
        *,
        tool: AIToolDefinition,
    ) -> AIToolContribution:
        """Declare one local executable tool for lifecycle registration."""

        for existing in self._tools:
            if existing.tool is tool:
                return existing
        contribution = AIToolContribution(tool=tool)
        self._tools.append(contribution)
        return contribution

    def register_skill_source(
        self,
        path: str | Path,
        *,
        base_path: str | Path | None = None,
    ) -> AISkillSourceContribution:
        """Declare a skill directory or ``SKILL.md`` file.

        Relative paths are resolved against ``base_path`` when supplied, or the
        current working directory for direct registry calls. Public helper
        functions below resolve omitted ``base_path`` values against the caller
        module directory.
        """

        resolved = _resolve_path(path, base_path=base_path)
        source = AISkillSourceContribution(path=resolved)
        self._skill_sources[resolved] = source
        return source

    def snapshot(self) -> AIContributionSnapshot:
        """Return deterministic declarations without mutating the registry."""

        return AIContributionSnapshot(
            tools=tuple(
                sorted(
                    self._tools,
                    key=lambda contribution: (
                        contribution.tool.name,
                        contribution.tool.origin,
                        contribution.tool.description,
                    ),
                )
            ),
            skill_sources=tuple(
                self._skill_sources[path] for path in sorted(self._skill_sources)
            ),
        )


ai_contributions = AIContributionRegistry()


def register_ai_skill_source(
    path: str | Path,
    *,
    base_path: str | Path | None = None,
) -> Path:
    """Register a plugin skill directory or file and return its resolved path."""

    if base_path is None:
        base_path = _caller_directory()
    return ai_contributions.register_skill_source(
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
    "AIContributionRegistry",
    "AIContributionSnapshot",
    "AISkillSourceContribution",
    "AIToolContribution",
    "ai_contributions",
    "register_ai_skill_source",
]
