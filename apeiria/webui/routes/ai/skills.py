"""AI prompt-skill routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_auth

from .skills_schemas import (
    AISkillItem,
    to_ai_skill_item,
)

router = APIRouter()


@router.get("/skills", response_model=list[AISkillItem])
async def list_ai_skills(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AISkillItem]:
    """List file-based prompt skills with runtime metadata."""

    skills = ai_application.skills.list_skills()
    return [to_ai_skill_item(item) for item in skills]


@router.post("/skills/reload", response_model=list[AISkillItem])
async def reload_ai_skills(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AISkillItem]:
    ai_application.skills.reload_skills()
    return [to_ai_skill_item(item) for item in ai_application.skills.list_skills()]


__all__ = ["router"]
