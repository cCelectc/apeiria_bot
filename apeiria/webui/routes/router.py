"""Core HTTP router aggregation (plugin-provided routers are added separately)."""

from fastapi import APIRouter

from apeiria.webui.routes.access import router as permission_router
from apeiria.webui.routes.adapter_config import router as adapter_config_router
from apeiria.webui.routes.adapter_selection import router as adapter_selection_router
from apeiria.webui.routes.adapter_store import router as adapter_store_router
from apeiria.webui.routes.ai.agents import router as ai_agents_router
from apeiria.webui.routes.ai.knowledge import router as ai_knowledge_router
from apeiria.webui.routes.ai.mcp_servers import router as ai_mcp_router
from apeiria.webui.routes.ai.memories import router as ai_memories_router
from apeiria.webui.routes.ai.models import router as ai_models_router
from apeiria.webui.routes.ai.personas import router as ai_personas_router
from apeiria.webui.routes.ai.profiles import router as ai_profiles_router
from apeiria.webui.routes.ai.relationships import router as ai_relationships_router
from apeiria.webui.routes.ai.sessions import router as ai_sessions_router
from apeiria.webui.routes.ai.skills import router as ai_skills_router
from apeiria.webui.routes.ai.tools import router as ai_tools_router
from apeiria.webui.routes.ai_settings import router as ai_settings_router
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
router.include_router(
    ai_settings_router,
    prefix="/ai/settings",
    tags=["ai-settings"],
)
router.include_router(ai_agents_router, prefix="/ai/agents", tags=["ai-agents"])
router.include_router(ai_mcp_router, prefix="/ai/mcp/servers", tags=["ai-mcp"])
router.include_router(ai_personas_router, prefix="/ai/personas", tags=["ai-personas"])
router.include_router(ai_profiles_router, prefix="/ai/profiles", tags=["ai-profiles"])
router.include_router(
    ai_relationships_router,
    prefix="/ai/relationships",
    tags=["ai-relationships"],
)
router.include_router(
    ai_memories_router,
    prefix="/ai/memories",
    tags=["ai-memories"],
)
router.include_router(
    ai_knowledge_router,
    prefix="/ai/knowledge",
    tags=["ai-knowledge"],
)
router.include_router(ai_models_router, prefix="/ai/models", tags=["ai-models"])
router.include_router(ai_sessions_router, prefix="/ai/sessions", tags=["ai-sessions"])
router.include_router(ai_tools_router, prefix="/ai/tools", tags=["ai-tools"])
router.include_router(ai_skills_router, prefix="/ai/skills", tags=["ai-skills"])
router.include_router(project_update_router, prefix="/update", tags=["update"])

__all__ = ["router"]
