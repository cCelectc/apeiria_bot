"""HTTP router aggregation entrypoint."""

from fastapi import APIRouter

from .ai_routes import router as ai_router
from .auth_routes import router as auth_router
from .chat_routes import router as chat_router
from .dashboard_routes import router as dashboard_router
from .log_routes import router as log_router
from .permission_routes import router as permission_router
from .plugin_catalog_routes import router as plugin_catalog_router
from .plugin_config_routes import router as plugin_config_router
from .plugin_management_routes import router as plugin_management_router
from .plugin_store_routes import router as plugin_store_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(ai_router, prefix="/ai", tags=["ai"])
router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
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

__all__ = ["router"]
