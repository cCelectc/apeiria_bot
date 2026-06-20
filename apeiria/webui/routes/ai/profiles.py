from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.ai_relationship import AIProfile
from apeiria.webui.auth import require_auth

router = APIRouter()


class ProfileResponse(BaseModel):
    id: int
    platform: str
    user_id: str
    display_name: str | None
    created_at: str
    updated_at: str


class ProfileCreate(BaseModel):
    platform: str
    user_id: str
    display_name: str | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = None


def _to_response(p: AIProfile) -> ProfileResponse:
    return ProfileResponse(
        id=p.id,
        platform=p.platform,
        user_id=p.user_id,
        display_name=p.display_name,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=list[ProfileResponse])
async def list_profiles(
    _: Annotated[Any, Depends(require_auth)],
) -> list[ProfileResponse]:
    async with get_session() as db:
        result = await db.execute(
            select(AIProfile).order_by(AIProfile.id.desc()),
        )
        return [_to_response(r) for r in result.scalars()]


@router.post("", response_model=ProfileResponse, status_code=201)
async def create_profile(
    body: ProfileCreate,
    _: Annotated[Any, Depends(require_auth)],
) -> ProfileResponse:
    async with get_session() as db:
        p = AIProfile(
            platform=body.platform,
            user_id=body.user_id,
            display_name=body.display_name,
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return _to_response(p)


@router.patch("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: int,
    body: ProfileUpdate,
    _: Annotated[Any, Depends(require_auth)],
) -> ProfileResponse:
    async with get_session() as db:
        p = await db.get(AIProfile, profile_id)
        if not p:
            raise HTTPException(404, "Profile not found")
        for key, val in body.model_dump(exclude_unset=True).items():
            setattr(p, key, val)
        await db.commit()
        await db.refresh(p)
        return _to_response(p)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    async with get_session() as db:
        p = await db.get(AIProfile, profile_id)
        if not p:
            raise HTTPException(404, "Profile not found")
        await db.delete(p)
        await db.commit()
