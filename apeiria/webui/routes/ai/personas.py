"""AI persona admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends

from apeiria.app.ai.admin.control_service import ai_control_admin_service
from apeiria.webui.auth import require_control_panel

from .schemas import (
    AIPersonaBindingItem,
    AIPersonaItem,
    AIPersonaUpsertRequest,
)
from .support import (
    to_ai_persona_binding_item,
    to_ai_persona_item,
)

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


def _actor_username_from_claims(session: "AuthSession") -> str | None:
    username = session.username.strip()
    return username or None


@router.get("/personas", response_model=list[AIPersonaItem])
async def list_ai_personas(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIPersonaItem]:
    personas = await ai_control_admin_service.list_personas()
    return [to_ai_persona_item(item) for item in personas]


@router.put("/personas", response_model=AIPersonaItem | None)
async def upsert_ai_persona(
    payload: AIPersonaUpsertRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIPersonaItem | None:
    persona = (
        await ai_control_admin_service.update_persona(
            persona_id=payload.persona_id,
            name=payload.name,
            description=payload.description,
            system_prompt=payload.system_prompt,
            style_prompt=payload.style_prompt,
            enabled=payload.enabled,
            actor_username=_actor_username_from_claims(session),
        )
        if payload.persona_id
        else await ai_control_admin_service.create_persona(
            name=payload.name,
            description=payload.description,
            system_prompt=payload.system_prompt,
            style_prompt=payload.style_prompt,
            enabled=payload.enabled,
            actor_username=_actor_username_from_claims(session),
        )
    )
    return to_ai_persona_item(persona) if persona is not None else None


@router.get("/persona-bindings", response_model=list[AIPersonaBindingItem])
async def list_ai_persona_bindings(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIPersonaBindingItem]:
    bindings = await ai_control_admin_service.list_persona_bindings()
    return [to_ai_persona_binding_item(item) for item in bindings]


__all__ = ["router"]
