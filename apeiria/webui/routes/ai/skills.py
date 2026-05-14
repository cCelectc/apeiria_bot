"""AI prompt-skill routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_control_panel

from .skills_schemas import AISkillItem, to_ai_skill_item

router = APIRouter()


@router.get("/skills", response_model=list[AISkillItem])
async def list_ai_skills(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AISkillItem]:
    """List file-based prompt skills."""

    skills = ai_application.skills.list_skills()
    return [to_ai_skill_item(item) for item in skills]


__all__ = ["router"]
