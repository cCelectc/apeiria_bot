"""AI admin routes — thin aggregator over per-domain sub-routers.

Each `/api/ai` endpoint family lives in its own module. This file just
composes them into a single `router` that the AI plugin mounts.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_control_panel

from .future_tasks import router as _future_tasks_router
from .knowledge import router as _knowledge_router
from .memories import router as _memories_router
from .models import router as _models_router
from .person_profiles import router as _person_profiles_router
from .personas import router as _personas_router
from .relationships import router as _relationships_router
from .sessions import router as _sessions_router
from .sources import router as _sources_router
from .sources_schemas import AIBootstrapResponse, to_ai_source_preset_item
from .tools import router as _tools_router
from .traces import router as _traces_router

router = APIRouter()


@router.get("/bootstrap", response_model=AIBootstrapResponse)
async def get_ai_bootstrap(
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIBootstrapResponse:
    return AIBootstrapResponse(
        source_presets=[
            to_ai_source_preset_item(item)
            for item in ai_application.operations.list_source_presets()
        ],
        scope_types=["conversation", "user", "group", "global"],
        task_classes=[
            "reply_default",
            "reply_roleplay",
            "tool_orchestration",
            "memory_extraction",
            "planner_light",
            "reasoning_heavy",
        ],
    )


router.include_router(_future_tasks_router)
router.include_router(_knowledge_router)
router.include_router(_memories_router)
router.include_router(_models_router)
router.include_router(_person_profiles_router)
router.include_router(_personas_router)
router.include_router(_relationships_router)
router.include_router(_sessions_router)
router.include_router(_sources_router)
router.include_router(_tools_router)
router.include_router(_traces_router)

__all__ = ["router"]
