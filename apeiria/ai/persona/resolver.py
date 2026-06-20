from __future__ import annotations

from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.ai_persona import Persona, PersonaBinding

FALLBACK_PERSONA_PROMPT = "你是一个友善的AI助手。"


async def resolve(session_id: str) -> Persona | None:
    async with get_session() as session:
        binding = (
            await session.execute(
                select(PersonaBinding).where(PersonaBinding.session_id == session_id)
            )
        ).scalar_one_or_none()
        if binding:
            persona = (
                await session.execute(
                    select(Persona).where(
                        Persona.id == binding.persona_id,
                        Persona.enabled == 1,
                    )
                )
            ).scalar_one_or_none()
            if persona:
                return persona

        return (
            await session.execute(
                select(Persona).where(
                    Persona.is_default == 1,
                    Persona.enabled == 1,
                )
            )
        ).scalar_one_or_none()
