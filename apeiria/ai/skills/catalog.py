"""Catalog models for LLM-visible prompt skills."""

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
