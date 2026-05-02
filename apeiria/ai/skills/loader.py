"""Filesystem loader for SKILL.md files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.skills.parser import (
    AISkillFileDefinition,
    SkillParseError,
    parse_skill_file,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

SKILL_FILENAME = "SKILL.md"


def load_skills_from_directory(root: Path) -> list[AISkillFileDefinition]:
    """Scan *root* recursively for ``SKILL.md`` files and parse them.

    Each immediate subdirectory (or the root itself) may contain a
    ``SKILL.md`` file.  Nested skills are supported::

        data/skills/
        ├── social-observer/
        │   └── SKILL.md
        ├── emotion-reader/
        │   └── SKILL.md
        └── translate/
            └── SKILL.md

    Files that fail to parse are logged and skipped rather than
    aborting the entire scan.

    Returns
    -------
    list[AISkillFileDefinition]
        Successfully parsed skill definitions, sorted by name.
    """

    skills = load_skills_from_sources((root,))
    logger.info("Loaded {} skill(s) from {}", len(skills), root)
    return skills


def load_skills_from_sources(
    sources: "Iterable[Path]",
) -> list[AISkillFileDefinition]:
    """Load skills from directories or individual ``SKILL.md`` files.

    Missing sources and malformed skill files are skipped so one bad plugin
    skill file cannot abort AI lifecycle initialization.
    """

    loaded_by_name: dict[str, AISkillFileDefinition] = {}
    for skill_file in _iter_skill_files(sources):
        skill = _try_load_skill_file(skill_file)
        if skill is not None:
            loaded_by_name[skill.skill_name] = skill
    return [loaded_by_name[name] for name in sorted(loaded_by_name)]


def _try_load_skill_file(
    skill_file: Path,
) -> AISkillFileDefinition | None:
    """Attempt to load a single skill file, returning None on failure."""

    try:
        content = skill_file.read_text(encoding="utf-8")
        definition = parse_skill_file(content, file_path=str(skill_file))
    except SkillParseError as exc:
        logger.warning("Skipping malformed skill file: {}", exc)
        return None
    except OSError as exc:
        logger.warning("Cannot read skill file {}: {}", skill_file, exc)
        return None

    logger.debug(
        "Loaded skill '{}' from {}",
        definition.skill_name,
        skill_file,
    )
    return definition


def _iter_skill_files(sources: "Iterable[Path]") -> list[Path]:
    skill_files: set[Path] = set()
    for source in sources:
        path = Path(source).resolve(strict=False)
        if path.is_dir():
            skill_files.update(
                item.resolve(strict=False) for item in path.rglob(SKILL_FILENAME)
            )
            continue
        if path.is_file() and path.name == SKILL_FILENAME:
            skill_files.add(path)
            continue
        logger.debug("Skill source does not exist or is not a SKILL.md file: {}", path)
    return sorted(skill_files)


def get_default_skills_directory() -> Path:
    """Return the default skills directory ``data/skills/``."""

    return Path("data") / "skills"
