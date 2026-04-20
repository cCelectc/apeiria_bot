"""Persona domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PersonaBindingScope = Literal["global", "group", "user", "conversation"]


@dataclass(frozen=True)
class AIPersonaCreateInput:
    """Create or update payload for one persona."""

    name: str
    description: str
    system_prompt: str
    style_prompt: str
    enabled: bool = True


@dataclass(frozen=True)
class AIPersonaDefinition:
    """Pure persona definition used by the AI domain."""

    persona_id: str
    name: str
    description: str
    system_prompt: str
    style_prompt: str
    enabled: bool = True


@dataclass(frozen=True)
class AIPersonaBindingSpec:
    """One resolved persona binding record."""

    binding_id: str
    scope_type: PersonaBindingScope
    scope_id: str
    persona_id: str


@dataclass(frozen=True)
class AIPersonaBindingTarget:
    """Binding target derived from the current AI scene."""

    conversation_id: str
    group_id: str | None
    user_id: str | None
