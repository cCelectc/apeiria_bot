"""Persona registry and binding service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from sqlalchemy import select

from apeiria.ai.persona.models import (
    AIPersonaBindingSpec,
    AIPersonaBindingTarget,
    AIPersonaCreateInput,
    AIPersonaDefinition,
    PersonaBindingScope,
)
from apeiria.ai.persona.resolver import resolve_persona_binding
from apeiria.db.models import AIPersona, AIPersonaBinding

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIPersonaPromptBundle:
    """Separated persona prompt channel for later prompt assembly."""

    persona_id: str
    name: str
    system_prompt: str
    style_prompt: str
    system_prompt_template: str
    style_prompt_template: str


@dataclass(frozen=True)
class AIPersonaRenderContext:
    """Stable template variables available during persona rendering."""

    bot_name: str
    bot_id: str
    current_time: datetime
    platform: str
    scene_type: str
    scene_id: str
    session_id: str
    scene_label: str
    group_name: str | None = None
    user_id: str | None = None
    user_name: str | None = None
    is_group_chat: bool = False
    is_private_chat: bool = False


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
        render_context: AIPersonaRenderContext | None = None,
    ) -> AIPersonaPromptBundle | None:
        """Build the persona-only prompt bundle for later assembly."""

        persona = await self.resolve_persona(session, target=target)
        if persona is None:
            return None
        return AIPersonaPromptBundle(
            persona_id=persona.persona_id,
            name=persona.name,
            system_prompt=render_persona_template(
                persona.system_prompt,
                render_context,
                extra_variables={"persona_name": persona.name},
            ),
            style_prompt=render_persona_template(
                persona.style_prompt,
                render_context,
                extra_variables={"persona_name": persona.name},
            ),
            system_prompt_template=persona.system_prompt,
            style_prompt_template=persona.style_prompt,
        )


def render_persona_template(
    template: str,
    render_context: AIPersonaRenderContext | None,
    *,
    extra_variables: dict[str, str] | None = None,
) -> str:
    """Render stable persona template variables without touching unknown braces."""

    if not template or render_context is None:
        return template
    rendered = template
    variables = _build_template_variables(render_context)
    if extra_variables:
        variables.update(extra_variables)
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def build_persona_render_context(  # noqa: PLR0913
    *,
    bot_id: str,
    current_time: datetime,
    platform: str,
    scene_type: str,
    scene_id: str,
    session_id: str,
    group_name: str | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
) -> AIPersonaRenderContext:
    normalized_group_name = (group_name or "").strip() or None
    scene_label = normalized_group_name or scene_id
    return AIPersonaRenderContext(
        bot_name=bot_id,
        bot_id=bot_id,
        current_time=current_time,
        platform=platform,
        scene_type=scene_type,
        scene_id=scene_id,
        session_id=session_id,
        scene_label=scene_label,
        group_name=normalized_group_name,
        user_id=user_id,
        user_name=user_name,
        is_group_chat=scene_type == "group",
        is_private_chat=scene_type == "private",
    )


def _build_template_variables(
    render_context: AIPersonaRenderContext,
) -> dict[str, str]:
    current_time_text = render_context.current_time.isoformat(timespec="seconds")
    return {
        "bot_name": render_context.bot_name,
        "bot_id": render_context.bot_id,
        "current_time": current_time_text,
        "current_date": current_time_text.split("T", maxsplit=1)[0],
        "platform": render_context.platform,
        "scene_type": render_context.scene_type,
        "scene_id": render_context.scene_id,
        "session_id": render_context.session_id,
        "scene_label": render_context.scene_label,
        "group_name": render_context.group_name or "",
        "user_id": render_context.user_id or "",
        "user_name": render_context.user_name or "",
        "is_group_chat": "true" if render_context.is_group_chat else "false",
        "is_private_chat": "true" if render_context.is_private_chat else "false",
    }


ai_persona_service = AIPersonaService()
