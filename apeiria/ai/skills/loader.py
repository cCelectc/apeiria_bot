"""Filesystem loader for SKILL.md files."""

from __future__ import annotations

from pathlib import Path

from nonebot.log import logger

from apeiria.ai.skills.parser import (
    AISkillFileDefinition,
    SkillParseError,
    parse_skill_file,
)

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

    if not root.is_dir():
        logger.debug("Skill directory does not exist: {}", root)
        return []

    skills: list[AISkillFileDefinition] = []

    for skill_file in root.rglob(SKILL_FILENAME):
        skill = _try_load_skill_file(skill_file)
        if skill is not None:
            skills.append(skill)

    skills.sort(key=lambda s: s.skill_name)
    logger.info("Loaded {} skill(s) from {}", len(skills), root)
    return skills


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


def get_default_skills_directory() -> Path:
    """Return the default skills directory ``data/skills/``."""

    return Path("data") / "skills"
