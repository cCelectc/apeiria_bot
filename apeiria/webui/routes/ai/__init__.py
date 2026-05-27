"""AI admin routes — thin aggregator over per-domain sub-routers.

Each `/api/ai` endpoint family lives in its own module. This file just
composes them into a single `router` that the Web UI control plane mounts.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_auth

from .future_tasks import router as _future_tasks_router
from .knowledge import router as _knowledge_router
from .memories import router as _memories_router
from .models import router as _models_router
from .personas import router as _personas_router
from .profiles import router as _profiles_router
from .relationships import router as _relationships_router
from .sessions import router as _sessions_router
from .settings import router as _settings_router
from .skills import router as _skills_router
from .sources import router as _sources_router
from .sources_schemas import (
    AIBootstrapResponse,
    AIRuntimeStatusResponse,
    to_ai_source_preset_item,
)
from .tools import router as _tools_router
from .traces import router as _traces_router
from .usage import router as _usage_router

router = APIRouter()

AI_RUNTIME_PLUGIN_MODULE = "apeiria.builtin_plugins.ai"


@router.get("/bootstrap", response_model=AIBootstrapResponse)
async def get_ai_bootstrap(
    _: Annotated[Any, Depends(require_auth)],
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


@router.get("/runtime-status", response_model=AIRuntimeStatusResponse)
async def get_ai_runtime_status(
    _: Annotated[Any, Depends(require_auth)],
) -> AIRuntimeStatusResponse:
    from apeiria.plugins.repository import plugin_catalog_repository

    lifecycle = ai_application.lifecycle.inspect()
    runtime_status = await ai_application.diagnostics.get_runtime_status()
    return AIRuntimeStatusResponse(
        configuration_api_available=True,
        runtime_plugin_module=AI_RUNTIME_PLUGIN_MODULE,
        runtime_plugin_enabled=(
            await plugin_catalog_repository.get_plugin_enabled(AI_RUNTIME_PLUGIN_MODULE)
        ),
        runtime_plugin_loaded=_is_ai_runtime_plugin_loaded(),
        lifecycle_initialized=bool(getattr(lifecycle, "initialized", False)),
        lifecycle_source=str(
            getattr(lifecycle, "initialization_source", "not_initialized")
        ),
        runtime_ready=runtime_status.ready,
        runtime_phase=runtime_status.phase,
        runtime_summary=runtime_status.summary,
    )


def _is_ai_runtime_plugin_loaded() -> bool:
    from apeiria.utils.plugin_introspection import find_loaded_plugin

    try:
        return find_loaded_plugin(AI_RUNTIME_PLUGIN_MODULE) is not None
    except ValueError:
        return False


router.include_router(_future_tasks_router)
router.include_router(_knowledge_router)
router.include_router(_memories_router)
router.include_router(_models_router)
router.include_router(_personas_router)
router.include_router(_profiles_router)
router.include_router(_relationships_router)
router.include_router(_sessions_router)
router.include_router(_settings_router)
router.include_router(_skills_router)
router.include_router(_sources_router)
router.include_router(_tools_router)
router.include_router(_traces_router)
router.include_router(_usage_router)

__all__ = ["router"]
