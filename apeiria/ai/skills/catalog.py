from __future__ import annotations

from typing import TYPE_CHECKING

import yaml
from nonebot.log import logger

if TYPE_CHECKING:
    from pathlib import Path

_skill_catalog: dict[str, dict[str, str]] = {}


def load_skills(directories: list[Path]) -> None:
    _skill_catalog.clear()
    for directory in directories:
        if not directory.exists():
            continue
        for skill_file in directory.rglob("SKILL.md"):
            try:
                _load_skill_file(skill_file)
            except Exception:  # noqa: BLE001, PERF203
                logger.warning(
                    "Failed to load skill: %s",
                    skill_file,
                    exc_info=True,
                )


def _load_skill_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return
    end = text.find("---", 3)
    if end == -1:
        return
    frontmatter = yaml.safe_load(text[3:end])
    if not isinstance(frontmatter, dict):
        return
    name = frontmatter.get("name")
    description = frontmatter.get("description", "")
    if not name:
        return
    body = text[end + 3 :].strip()
    _skill_catalog[name] = {
        "description": description,
        "body": body,
    }


def get_skill_names() -> list[tuple[str, str]]:
    return [(name, info["description"]) for name, info in _skill_catalog.items()]


def get_skill_body(name: str) -> str | None:
    info = _skill_catalog.get(name)
    return info["body"] if info else None
