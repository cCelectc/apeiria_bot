"""Schema models for AI persona routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.ai.persona import AIPersonaBindingSpec, AIPersonaDefinition


class AIPersonaItem(BaseModel):
    persona_id: str
    name: str
    description: str
    system_prompt: str
    style_prompt: str
    enabled: bool


class AIPersonaBindingItem(BaseModel):
    binding_id: str
    scope_type: str
    scope_id: str
    persona_id: str


class AIPersonaUpsertRequest(BaseModel):
    persona_id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2000)
    system_prompt: str = Field(min_length=1, max_length=20000)
    style_prompt: str = Field(default="", max_length=20000)
    enabled: bool = True


def to_ai_persona_item(item: "AIPersonaDefinition") -> AIPersonaItem:
    return AIPersonaItem(
        persona_id=item.persona_id,
        name=item.name,
        description=item.description,
        system_prompt=item.system_prompt,
        style_prompt=item.style_prompt,
        enabled=item.enabled,
    )


def to_ai_persona_binding_item(item: "AIPersonaBindingSpec") -> AIPersonaBindingItem:
    return AIPersonaBindingItem(
        binding_id=item.binding_id,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        persona_id=item.persona_id,
    )
