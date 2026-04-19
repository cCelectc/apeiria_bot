"""Persona admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot_plugin_orm import get_session

from apeiria.app.ai.admin.audit import record_ai_admin_audit
from apeiria.app.ai.persona.models import AIPersonaCreateInput
from apeiria.app.ai.persona.service import ai_persona_service

if TYPE_CHECKING:
    from apeiria.app.ai.persona.models import (
        AIPersonaBindingSpec,
        AIPersonaDefinition,
    )


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
        async with get_session() as session:
            return await ai_persona_service.list_personas(session)

    async def list_persona_bindings(self) -> list["AIPersonaBindingSpec"]:
        async with get_session() as session:
            return await ai_persona_service.list_bindings(session)

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
        async with get_session() as session:
            row = await ai_persona_service.create_persona(
                session,
                _build_persona_create_input(
                    name=name,
                    description=description,
                    system_prompt=system_prompt,
                    style_prompt=style_prompt,
                    enabled=enabled,
                ),
            )
            await session.commit()
            personas = await ai_persona_service.list_personas(session)
            created = next(
                item for item in personas if item.persona_id == row.persona_id
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
        async with get_session() as session:
            row = await ai_persona_service.update_persona(
                session,
                persona_id=persona_id,
                create_input=_build_persona_create_input(
                    name=name,
                    description=description,
                    system_prompt=system_prompt,
                    style_prompt=style_prompt,
                    enabled=enabled,
                ),
            )
            if row is None:
                return None
            await session.commit()
            personas = await ai_persona_service.list_personas(session)
            updated = next(
                (item for item in personas if item.persona_id == persona_id),
                None,
            )
            if updated is not None:
                record_ai_admin_audit(
                    "ai_persona_updated",
                    actor_username=actor_username,
                    detail=f"{updated.persona_id} {updated.name}",
                )
            return updated


__all__ = ["PersonasAdminMixin"]
