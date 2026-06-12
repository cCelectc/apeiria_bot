"""Persona registry and binding service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from datetime import datetime

from sqlalchemy import select, update

from apeiria.ai.persona.models import (
    AIPersonaBindingSpec,
    AIPersonaBindingTarget,
    AIPersonaCreateInput,
    AIPersonaDefinition,
    PersonaBindingScope,
)
from apeiria.ai.persona.resolver import resolve_persona_binding
from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session
from apeiria.db.models.ai_persona import AIPersona, AIPersonaBinding


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
        *,
        include_disabled: bool = True,
    ) -> list[AIPersonaDefinition]:
        """List personas from storage."""
        async with get_session() as session:
            result = await session.execute(
                select(AIPersona).order_by(AIPersona.name, AIPersona.persona_id)
            )
            rows = result.scalars().all()
        return [
            AIPersonaDefinition(
                persona_id=r.persona_id,
                name=r.name,
                description=r.description,
                system_prompt=r.system_prompt,
                style_prompt=r.style_prompt,
                enabled=bool(r.enabled),
            )
            for r in rows
            if include_disabled or bool(r.enabled)
        ]

    async def list_bindings(
        self,
    ) -> list[AIPersonaBindingSpec]:
        """List persona bindings from storage."""
        async with get_session() as session:
            result = await session.execute(
                select(AIPersonaBinding).order_by(AIPersonaBinding.binding_id)
            )
            rows = result.scalars().all()
        return [
            AIPersonaBindingSpec(
                binding_id=r.binding_id,
                scope_type=cast("PersonaBindingScope", r.scope_type),
                scope_id=r.scope_id,
                persona_id=r.persona_id,
            )
            for r in rows
        ]

    async def resolve_persona(
        self,
        *,
        target: AIPersonaBindingTarget,
    ) -> AIPersonaDefinition | None:
        """Resolve the effective persona definition for one AI scene."""

        personas = await self.list_personas(include_disabled=False)
        persona_map = {persona.persona_id: persona for persona in personas}
        bindings = await self.list_bindings()
        binding = resolve_persona_binding(bindings, target)
        if binding is None:
            return None
        return persona_map.get(binding.persona_id)

    async def get_persona(
        self,
        *,
        persona_id: str,
        include_disabled: bool = False,
    ) -> AIPersonaDefinition | None:
        """Load one persona definition by id."""

        for persona in await self.list_personas(include_disabled=include_disabled):
            if persona.persona_id == persona_id:
                return persona
        return None

    async def create_persona(
        self,
        create_input: AIPersonaCreateInput,
    ) -> AIPersonaDefinition:
        import uuid

        persona = AIPersonaDefinition(
            persona_id=f"persona_{uuid.uuid4().hex}",
            name=create_input.name,
            description=create_input.description,
            system_prompt=create_input.system_prompt,
            style_prompt=create_input.style_prompt,
            enabled=create_input.enabled,
        )
        now = _epoch_ms()
        async with get_session() as session:
            session.add(
                AIPersona(
                    persona_id=persona.persona_id,
                    name=persona.name,
                    description=persona.description,
                    system_prompt=persona.system_prompt,
                    style_prompt=persona.style_prompt,
                    enabled=1 if persona.enabled else 0,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
        return persona

    async def update_persona(
        self,
        *,
        persona_id: str,
        create_input: AIPersonaCreateInput,
    ) -> AIPersonaDefinition | None:
        existing_persona = next(
            (
                persona
                for persona in await self.list_personas(include_disabled=True)
                if persona.persona_id == persona_id
            ),
        )
        if existing_persona is None:
            return None
        updated = AIPersonaDefinition(
            persona_id=persona_id,
            name=create_input.name,
            description=create_input.description,
            system_prompt=create_input.system_prompt,
            style_prompt=create_input.style_prompt,
            enabled=create_input.enabled,
        )
        async with get_session() as session:
            await session.execute(
                update(AIPersona)
                .where(AIPersona.persona_id == persona_id)
                .values(
                    name=updated.name,
                    description=updated.description,
                    system_prompt=updated.system_prompt,
                    style_prompt=updated.style_prompt,
                    enabled=1 if updated.enabled else 0,
                    updated_at=_epoch_ms(),
                )
            )
            await session.commit()
        return updated

    async def build_persona_prompt_bundle(
        self,
        *,
        target: AIPersonaBindingTarget,
        render_context: AIPersonaRenderContext | None = None,
    ) -> AIPersonaPromptBundle | None:
        """Build the persona-only prompt bundle for later assembly."""

        persona = await self.resolve_persona(target=target)
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

    async def build_persona_prompt_bundle_by_id(
        self,
        *,
        persona_id: str,
        render_context: AIPersonaRenderContext | None = None,
    ) -> AIPersonaPromptBundle | None:
        """Build a persona prompt bundle from an explicit persona id."""

        persona = await self.get_persona(
            persona_id=persona_id,
            include_disabled=False,
        )
        if persona is None:
            return None
        return _build_persona_prompt_bundle(
            persona,
            render_context=render_context,
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


def _build_persona_prompt_bundle(
    persona: AIPersonaDefinition,
    *,
    render_context: AIPersonaRenderContext | None,
) -> AIPersonaPromptBundle:
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
