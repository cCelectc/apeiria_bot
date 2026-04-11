"""Persona registry and binding service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from sqlalchemy import select

from apeiria.app.ai.persona.models import (
    AIPersonaBindingSpec,
    AIPersonaBindingTarget,
    AIPersonaCreateInput,
    AIPersonaDefinition,
    PersonaBindingScope,
)
from apeiria.app.ai.persona.resolver import resolve_persona_binding
from apeiria.infra.db.models import AIPersona, AIPersonaBinding

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIPersonaPromptBundle:
    """Separated persona prompt channel for later prompt assembly."""

    persona_id: str
    system_prompt: str
    style_prompt: str


class AIPersonaService:
    """Persona registry and binding lookup service."""

    async def list_personas(
        self,
        session: AsyncSession,
        *,
        include_disabled: bool = True,
    ) -> list[AIPersonaDefinition]:
        """List personas from storage."""

        query = select(AIPersona)
        if not include_disabled:
            query = query.where(AIPersona.enabled.is_(True))
        result = await session.execute(query.order_by(AIPersona.id.asc()))
        return [
            AIPersonaDefinition(
                persona_id=row.persona_id,
                name=row.name,
                description=row.description,
                system_prompt=row.system_prompt,
                style_prompt=row.style_prompt,
                enabled=row.enabled,
            )
            for row in result.scalars().all()
        ]

    async def list_bindings(self, session: AsyncSession) -> list[AIPersonaBindingSpec]:
        """List persona bindings from storage."""

        result = await session.execute(
            select(AIPersonaBinding).order_by(AIPersonaBinding.id.asc())
        )
        return [
            AIPersonaBindingSpec(
                binding_id=row.binding_id,
                scope_type=cast("PersonaBindingScope", row.scope_type),
                scope_id=row.scope_id,
                persona_id=row.persona_id,
            )
            for row in result.scalars().all()
        ]

    async def resolve_persona(
        self,
        session: AsyncSession,
        *,
        target: AIPersonaBindingTarget,
    ) -> AIPersonaDefinition | None:
        """Resolve the effective persona definition for one AI scene."""

        personas = await self.list_personas(session, include_disabled=False)
        persona_map = {persona.persona_id: persona for persona in personas}
        bindings = await self.list_bindings(session)
        binding = resolve_persona_binding(bindings, target)
        if binding is None:
            return None
        return persona_map.get(binding.persona_id)

    async def create_persona(
        self,
        session: AsyncSession,
        create_input: AIPersonaCreateInput,
    ) -> AIPersona:
        row = AIPersona(
            persona_id=f"persona_{__import__('uuid').uuid4().hex}",
            name=create_input.name,
            description=create_input.description,
            system_prompt=create_input.system_prompt,
            style_prompt=create_input.style_prompt,
            enabled=create_input.enabled,
        )
        session.add(row)
        await session.flush()
        return row

    async def update_persona(
        self,
        session: AsyncSession,
        *,
        persona_id: str,
        create_input: AIPersonaCreateInput,
    ) -> AIPersona | None:
        result = await session.execute(
            select(AIPersona).where(AIPersona.persona_id == persona_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.name = create_input.name
        row.description = create_input.description
        row.system_prompt = create_input.system_prompt
        row.style_prompt = create_input.style_prompt
        row.enabled = create_input.enabled
        await session.flush()
        return row

    async def build_persona_prompt_bundle(
        self,
        session: AsyncSession,
        *,
        target: AIPersonaBindingTarget,
    ) -> AIPersonaPromptBundle | None:
        """Build the persona-only prompt bundle for later assembly."""

        persona = await self.resolve_persona(session, target=target)
        if persona is None:
            return None
        return AIPersonaPromptBundle(
            persona_id=persona.persona_id,
            system_prompt=persona.system_prompt,
            style_prompt=persona.style_prompt,
        )


ai_persona_service = AIPersonaService()
