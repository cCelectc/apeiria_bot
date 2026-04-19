"""AI person-profile admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, cast

from fastapi import APIRouter, Depends, Query

from apeiria.app.ai.admin.service import ai_admin_service
from apeiria.interfaces.http.auth import require_control_panel
from apeiria.interfaces.http.routes.ai_route_support import to_ai_person_profile_item
from apeiria.interfaces.http.schemas.ai_models import (
    AIPersonProfileItem,
    AIPersonProfileUpdateRequest,
)

if TYPE_CHECKING:
    from apeiria.shared.principal import AuthSession


router = APIRouter()


def _actor_username_from_claims(session: "AuthSession") -> str | None:
    username = session.username.strip()
    return username or None


@router.get("/person-profiles", response_model=list[AIPersonProfileItem])
async def list_ai_person_profiles(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AIPersonProfileItem]:
    profiles = await ai_admin_service.list_person_profiles(limit=limit)
    return [to_ai_person_profile_item(item) for item in profiles]


@router.get("/person-profiles/detail", response_model=AIPersonProfileItem | None)
async def get_ai_person_profile(
    _: Annotated[Any, Depends(require_control_panel)],
    platform: Annotated[str, Query(min_length=1)],
    user_id: Annotated[str, Query(min_length=1)],
) -> AIPersonProfileItem | None:
    profile = await ai_admin_service.get_person_profile(
        platform=platform,
        user_id=user_id,
    )
    return to_ai_person_profile_item(profile) if profile is not None else None


@router.patch("/person-profiles", response_model=AIPersonProfileItem | None)
async def update_ai_person_profile(
    payload: AIPersonProfileUpdateRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIPersonProfileItem | None:
    from apeiria.app.ai.person.models import (
        AIPersonMemoryPoint,
        AIPersonMemoryPointCategory,
    )

    memory_points = None
    if payload.memory_points is not None:
        memory_points = tuple(
            AIPersonMemoryPoint(
                category=cast("AIPersonMemoryPointCategory", point.category),
                content=point.content,
                confidence=point.confidence,
                source_message_id=point.source_message_id,
            )
            for point in payload.memory_points
        )
    profile = await ai_admin_service.update_person_profile(
        person_id=payload.person_id,
        person_name=payload.person_name,
        nickname=payload.nickname,
        memory_points=memory_points,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_person_profile_item(profile) if profile is not None else None


@router.delete("/person-profiles", response_model=bool)
async def delete_ai_person_profile(
    session: Annotated["AuthSession", Depends(require_control_panel)],
    person_id: Annotated[str, Query(min_length=1)],
) -> bool:
    return await ai_admin_service.delete_person_profile(
        person_id=person_id,
        actor_username=_actor_username_from_claims(session),
    )


__all__ = ["router"]
