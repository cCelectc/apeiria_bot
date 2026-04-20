"""AI admin routes — thin aggregator over per-domain sub-routers.

Each `/api/ai` endpoint family lives in its own module. This file just
composes them into a single `router` that `routes/router.py` mounts at
`/api/ai`.
"""

from __future__ import annotations

from fastapi import APIRouter

from apeiria.ai.webui.routes.future_tasks import (
    router as _future_tasks_router,
)
from apeiria.ai.webui.routes.memories import (
    router as _memories_router,
)
from apeiria.ai.webui.routes.models import router as _models_router
from apeiria.ai.webui.routes.person_profiles import (
    router as _person_profiles_router,
)
from apeiria.ai.webui.routes.personas import (
    router as _personas_router,
)
from apeiria.ai.webui.routes.relationships import (
    router as _relationships_router,
)
from apeiria.ai.webui.routes.sessions import (
    router as _sessions_router,
)
from apeiria.ai.webui.routes.sources import (
    router as _sources_router,
)
from apeiria.ai.webui.routes.tools import router as _tools_router

router = APIRouter()
router.include_router(_future_tasks_router)
router.include_router(_memories_router)
router.include_router(_models_router)
router.include_router(_person_profiles_router)
router.include_router(_personas_router)
router.include_router(_relationships_router)
router.include_router(_sessions_router)
router.include_router(_sources_router)
router.include_router(_tools_router)

__all__ = ["router"]
