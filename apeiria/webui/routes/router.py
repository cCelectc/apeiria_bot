"""Core HTTP router aggregation (plugin-provided routers are added separately)."""

from fastapi import APIRouter

from apeiria.webui.routes.access import router as permission_router
from apeiria.webui.routes.adapter_config import router as adapter_config_router
from apeiria.webui.routes.adapter_selection import router as adapter_selection_router
from apeiria.webui.routes.adapter_store import router as adapter_store_router
from apeiria.webui.routes.ai import router as ai_router
from apeiria.webui.routes.auth import router as auth_router
from apeiria.webui.routes.chat import router as chat_router
from apeiria.webui.routes.core_config import router as core_config_router
from apeiria.webui.routes.dashboard import router as dashboard_router
from apeiria.webui.routes.driver_config import router as driver_config_router
from apeiria.webui.routes.logs import router as log_router
from apeiria.webui.routes.plugin_catalog import router as plugin_catalog_router
from apeiria.webui.routes.plugin_config import router as plugin_config_router
from apeiria.webui.routes.plugin_management import router as plugin_management_router
from apeiria.webui.routes.plugin_store import router as plugin_store_router
from apeiria.webui.routes.project_update import router as project_update_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
router.include_router(core_config_router, prefix="/core", tags=["core-config"])
router.include_router(
    adapter_config_router,
    prefix="/adapters",
    tags=["adapter-config"],
)
router.include_router(
    adapter_selection_router,
    prefix="/adapters/selection",
    tags=["adapter-selection"],
)
router.include_router(
    adapter_store_router,
    prefix="/adapters/store",
    tags=["adapter-store"],
)
router.include_router(
    driver_config_router,
    prefix="/drivers",
    tags=["driver-config"],
)
router.include_router(
    plugin_store_router,
    prefix="/plugins/store",
    tags=["plugin-store"],
)
router.include_router(plugin_catalog_router, prefix="/plugins", tags=["plugins"])
router.include_router(plugin_config_router, prefix="/plugins", tags=["plugins"])
router.include_router(plugin_management_router, prefix="/plugins", tags=["plugins"])
router.include_router(permission_router, prefix="/permissions", tags=["permissions"])
router.include_router(log_router, prefix="/logs", tags=["logs"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])
router.include_router(ai_router, prefix="/ai", tags=["ai"])
router.include_router(project_update_router, prefix="/update", tags=["update"])

__all__ = ["router"]
