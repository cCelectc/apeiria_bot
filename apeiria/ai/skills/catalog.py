"""Catalog and admin models for file-based prompt skills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AISkillMetadata:
    """Product-facing prompt skill metadata for admin and catalog reads."""

    name: str
    description: str
    origin: Literal["file"] = "file"
    entry_mode: str = "prompt_only"
    tags: tuple[str, ...] = ()
    source_path: str = ""
    required_tools: tuple[str, ...] = ()
    loaded: bool = True
    selectable_now: bool = True
    display_name: str = ""
    display_description: str = ""
    error: str | None = None
