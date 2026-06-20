from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apeiria.ai.skills.catalog import get_skill_body, get_skill_names
from apeiria.webui.auth import require_auth

router = APIRouter()


class SkillItem(BaseModel):
    name: str
    description: str


class SkillDetail(BaseModel):
    name: str
    description: str
    body: str


@router.get("", response_model=list[SkillItem])
async def list_skills(
    _: Annotated[Any, Depends(require_auth)],
) -> list[SkillItem]:
    names = dict(get_skill_names())
    return [SkillItem(name=n, description=names[n]) for n in list(names)[:200]]


@router.get("/{name:path}", response_model=SkillDetail)
async def get_skill(
    name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> SkillDetail:
    body = get_skill_body(name)
    if not body:
        return SkillDetail(name=name, description="", body="")
    names = dict(get_skill_names())
    return SkillDetail(
        name=name,
        description=names.get(name, ""),
        body=body,
    )
