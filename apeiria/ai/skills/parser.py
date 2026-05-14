"""SKILL.md file parser with YAML frontmatter extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import yaml

SkillEntryMode = Literal["prompt_only", "workflow"]


@dataclass(frozen=True)
class AISkillFileDefinition:
    """Parsed representation of a single SKILL.md file."""

    skill_name: str
    description: str
    version: int
    triggers: tuple[str, ...]
    permissions: tuple[str, ...]
    entry_mode: SkillEntryMode
    body_markdown: str
    file_path: str
    tools: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class SkillParseError(ValueError):
    """Raised when a SKILL.md file cannot be parsed."""

    def __init__(self, file_path: str, detail: str) -> None:
        super().__init__(f"{file_path}: {detail}")
        self.file_path = file_path
        self.detail = detail


_REQUIRED_FIELDS = frozenset({"name", "description"})
_VALID_ENTRY_MODES: frozenset[str] = frozenset({"prompt_only", "workflow"})


def parse_skill_file(
    content: str,
    *,
    file_path: str = "<unknown>",
) -> AISkillFileDefinition:
    """Parse a SKILL.md file into an ``AISkillFileDefinition``.

    The file format is YAML frontmatter delimited by ``---`` followed by
    a markdown body::

        ---
        name: my-skill
        description: Short description
        version: 1
        triggers:
          - keyword1
          - keyword2
        permissions:
          - read_memory
        entry_mode: prompt_only
        ---

        # Skill body in markdown ...

    Parameters
    ----------
    content:
        Raw text content of the SKILL.md file.
    file_path:
        Path to the file (used for error messages).

    Returns
    -------
    AISkillFileDefinition

    Raises
    ------
    SkillParseError
        If the frontmatter is missing, malformed, or lacks required
        fields.
    """

    frontmatter_raw, body = _split_frontmatter(content, file_path=file_path)
    meta = _parse_yaml_frontmatter(frontmatter_raw, file_path=file_path)
    _validate_required_fields(meta, file_path=file_path)

    entry_mode = meta.get("entry_mode", "prompt_only")
    if entry_mode not in _VALID_ENTRY_MODES:
        raise SkillParseError(
            file_path,
            f"invalid entry_mode '{entry_mode}', "
            f"expected one of {sorted(_VALID_ENTRY_MODES)}",
        )

    return AISkillFileDefinition(
        skill_name=str(meta["name"]),
        description=str(meta["description"]),
        version=int(meta.get("version", 1)),
        triggers=_to_str_tuple(meta.get("triggers", [])),
        permissions=_to_str_tuple(meta.get("permissions", [])),
        entry_mode=entry_mode,  # type: ignore[arg-type]
        body_markdown=body.strip(),
        file_path=file_path,
        tools=_to_str_tuple(meta.get("tools", [])),
        tags=_to_str_tuple(meta.get("tags", [])),
    )


def _split_frontmatter(
    content: str,
    *,
    file_path: str,
) -> tuple[str, str]:
    """Split ``---`` delimited YAML frontmatter from body."""

    stripped = content.strip()
    if not stripped.startswith("---"):
        raise SkillParseError(
            file_path,
            "missing YAML frontmatter (must start with '---')",
        )

    end_index = stripped.find("---", 3)
    if end_index == -1:
        raise SkillParseError(
            file_path,
            "unclosed YAML frontmatter (missing closing '---')",
        )

    frontmatter = stripped[3:end_index].strip()
    body = stripped[end_index + 3 :]
    return frontmatter, body


def _parse_yaml_frontmatter(
    raw: str,
    *,
    file_path: str,
) -> dict[str, Any]:
    """Parse YAML frontmatter string into a dict."""

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SkillParseError(file_path, f"invalid YAML frontmatter: {exc}") from exc

    if not isinstance(parsed, dict):
        raise SkillParseError(
            file_path,
            f"YAML frontmatter must be a mapping, got {type(parsed).__name__}",
        )
    return parsed


def _validate_required_fields(
    meta: dict[str, Any],
    *,
    file_path: str,
) -> None:
    """Ensure required frontmatter fields are present."""

    missing = _REQUIRED_FIELDS - set(meta)
    if missing:
        raise SkillParseError(
            file_path,
            f"missing required fields: {sorted(missing)}",
        )


def _to_str_tuple(value: Any) -> tuple[str, ...]:
    """Coerce a list/string/None into a tuple of strings."""

    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return (str(value),)
