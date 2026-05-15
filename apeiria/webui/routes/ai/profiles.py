"""AI profile admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.ai.profile import AIProfileUpdateInput
from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_control_panel

from .profiles_schemas import (
    AIProfileItem,
    AIProfileUpdateRequest,
    to_ai_profile_item,
)

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


def _actor_username_from_claims(session: "AuthSession") -> str | None:
    username = session.username.strip()
    return username or None


@router.get("/profiles", response_model=list[AIProfileItem])
async def list_ai_profiles(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AIProfileItem]:
    profiles = await ai_application.operations.list_user_profiles(limit=limit)
    return [to_ai_profile_item(item) for item in profiles]


@router.get("/profiles/detail", response_model=AIProfileItem | None)
async def get_ai_profile(
    _: Annotated[Any, Depends(require_control_panel)],
    platform: Annotated[str, Query(min_length=1)],
    user_id: Annotated[str, Query(min_length=1)],
) -> AIProfileItem | None:
    profile = await ai_application.operations.get_user_profile(
        platform=platform,
        user_id=user_id,
    )
    return to_ai_profile_item(profile) if profile is not None else None


@router.patch("/profiles", response_model=AIProfileItem | None)
async def update_ai_profile(
    payload: AIProfileUpdateRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIProfileItem | None:
    update_fields: dict[str, Any] = {
        "name_visibility": payload.name_visibility,
        "profile_enabled": payload.profile_enabled,
    }
    for field_name in ("display_name", "preferred_name", "name_source"):
        if field_name in payload.model_fields_set:
            update_fields[field_name] = getattr(payload, field_name)
    profile = await ai_application.operations.update_user_profile(
        profile_id=payload.profile_id,
        update_input=AIProfileUpdateInput(**update_fields),
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_profile_item(profile) if profile is not None else None


@router.delete("/profiles", response_model=bool)
async def delete_ai_profile(
    session: Annotated["AuthSession", Depends(require_control_panel)],
    profile_id: Annotated[str, Query(min_length=1)],
) -> bool:
    return await ai_application.operations.delete_user_profile(
        profile_id=profile_id,
        actor_username=_actor_username_from_claims(session),
    )


__all__ = ["router"]
