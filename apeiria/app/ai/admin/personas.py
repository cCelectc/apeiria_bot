"""Persona admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.persona import AIPersonaCreateInput, ai_persona_service
from apeiria.app.ai.admin.audit import record_ai_admin_audit

if TYPE_CHECKING:
    from apeiria.ai.persona import AIPersonaBindingSpec, AIPersonaDefinition


def _build_persona_create_input(
    *,
    name: str,
    description: str,
    system_prompt: str,
    style_prompt: str,
    enabled: bool,
) -> AIPersonaCreateInput:
    return AIPersonaCreateInput(
        name=name,
        description=description,
        system_prompt=system_prompt,
        style_prompt=style_prompt,
        enabled=enabled,
    )


class PersonasAdminMixin:
    """Admin CRUD for AI personas and their scope bindings."""

    async def list_personas(self) -> list["AIPersonaDefinition"]:
        return await ai_persona_service.list_personas()

    async def list_persona_bindings(self) -> list["AIPersonaBindingSpec"]:
        return await ai_persona_service.list_bindings()

    async def create_persona(  # noqa: PLR0913
        self,
        *,
        name: str,
        description: str,
        system_prompt: str,
        style_prompt: str,
        enabled: bool,
        actor_username: str | None = None,
    ) -> "AIPersonaDefinition":
        created = await ai_persona_service.create_persona(
            _build_persona_create_input(
                name=name,
                description=description,
                system_prompt=system_prompt,
                style_prompt=style_prompt,
                enabled=enabled,
            ),
        )
        record_ai_admin_audit(
            "ai_persona_created",
            actor_username=actor_username,
            detail=f"{created.persona_id} {created.name}",
        )
        return created

    async def update_persona(  # noqa: PLR0913
        self,
        *,
        persona_id: str,
        name: str,
        description: str,
        system_prompt: str,
        style_prompt: str,
        enabled: bool,
        actor_username: str | None = None,
    ) -> "AIPersonaDefinition | None":
        updated = await ai_persona_service.update_persona(
            persona_id=persona_id,
            create_input=_build_persona_create_input(
                name=name,
                description=description,
                system_prompt=system_prompt,
                style_prompt=style_prompt,
                enabled=enabled,
            ),
        )
        if updated is not None:
            record_ai_admin_audit(
                "ai_persona_updated",
                actor_username=actor_username,
                detail=f"{updated.persona_id} {updated.name}",
            )
        return updated


__all__ = ["PersonasAdminMixin"]
